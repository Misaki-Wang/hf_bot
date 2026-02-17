#!/usr/bin/env python3
"""Translate summary_en into summary_zh for archived paper JSON files."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

import requests


class Translator(Protocol):
    def translate(self, text: str) -> str:
        ...

    def summarize_abstract(self, text: str) -> str:
        ...


PLACEHOLDER_RE = re.compile(r"^\$[0-9a-zA-Z]+$")


def normalize_text(value: str) -> str:
    return " ".join((value or "").split()).strip()


def trim_text(value: str, limit: int) -> str:
    text = normalize_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def has_meaningful_abstract(value: str) -> bool:
    text = normalize_text(value)
    if not text:
        return False
    if PLACEHOLDER_RE.match(text):
        return False
    return len(text) >= 48


@dataclass
class DummyTranslator:
    """Fallback translator that keeps pipeline runnable without API keys."""

    marker: str = "[DUMMY-TRANSLATION]"

    def translate(self, text: str) -> str:
        cleaned = normalize_text(text)
        if not cleaned:
            return ""
        return (
            f"{self.marker} 未配置真实翻译服务，以下保留英文原文。\n"
            f"{cleaned}"
        )

    def summarize_abstract(self, text: str) -> str:
        cleaned = normalize_text(text)
        if not cleaned:
            return ""
        parts = re.split(r"(?<=[.!?])\s+", cleaned)
        concise = " ".join(part.strip() for part in parts[:3] if part.strip())
        return trim_text(concise or cleaned, 520)


@dataclass
class OpenRouterTranslator:
    api_key: str
    model: str = "moonshotai/kimi-k2.5"
    timeout: float = 30.0
    endpoint: str = "https://openrouter.ai/api/v1/chat/completions"
    app_name: str = "hf-papers-archive"
    app_url: str = "https://github.com/your-org/hf-papers-archive"

    def _chat(self, messages: list[dict[str, str]], temperature: float) -> str:
        payload = {"model": self.model, "messages": messages, "temperature": temperature, "stream": False}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.app_url,
            "X-Title": self.app_name,
        }
        last_error: Exception | None = None

        for attempt in range(1, 4):
            try:
                response = requests.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                body = response.json()
                choices = body.get("choices", [])
                if not choices:
                    raise RuntimeError("OpenRouter response does not include choices")
                message = choices[0].get("message", {})
                raw_content = message.get("content", "")
                if isinstance(raw_content, list):
                    parts: list[str] = []
                    for item in raw_content:
                        if isinstance(item, dict):
                            text_part = str(item.get("text", "")).strip()
                            if text_part:
                                parts.append(text_part)
                    result = "\n".join(parts).strip()
                else:
                    result = str(raw_content).strip()
                if not result:
                    raise RuntimeError("OpenRouter response content is empty")
                return result
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < 3:
                    time.sleep(1.2 * attempt)
                    continue
        raise RuntimeError(f"OpenRouter request failed after retries: {last_error}")

    def summarize_abstract(self, text: str) -> str:
        content = normalize_text(text)
        if not content:
            return ""
        return self._chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI paper editor. Produce concise, faithful English summaries from abstracts. "
                        "Keep key technical terms, model names, datasets, and abbreviations unchanged."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Summarize the following abstract into 2-4 English sentences.\n"
                        "Requirements: factual, concise, no markdown, no bullet points, no hype.\n\n"
                        f"Abstract:\n{content}"
                    ),
                },
            ],
            temperature=0.2,
        )

    def translate(self, text: str) -> str:
        content = normalize_text(text)
        if not content:
            return ""
        return self._chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a technical translator for AI papers. Translate English summaries "
                        "into Simplified Chinese. Keep technical terms, model names, metrics, "
                        "datasets, and abbreviations (e.g., RLHF, GPU, UGA) unchanged whenever possible. "
                        "Do not omit information. Keep wording accurate and concise."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Translate the following summary to Chinese:\n\n"
                        f"{content}"
                    ),
                },
            ],
            temperature=0.1,
        )


def choose_translator(provider: str, model_override: str = "") -> Translator:
    provider = provider.lower()
    selected_model = model_override.strip()
    if provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            logging.warning("OPENROUTER_API_KEY not set; fallback to dummy translator")
            return DummyTranslator()
        model = selected_model or os.getenv("OPENROUTER_MODEL", "moonshotai/kimi-k2.5").strip() or "moonshotai/kimi-k2.5"
        app_name = os.getenv("OPENROUTER_APP_NAME", "hf-papers-archive").strip() or "hf-papers-archive"
        app_url = (
            os.getenv("OPENROUTER_APP_URL", "https://github.com/your-org/hf-papers-archive").strip()
            or "https://github.com/your-org/hf-papers-archive"
        )
        return OpenRouterTranslator(api_key=api_key, model=model, app_name=app_name, app_url=app_url)

    if provider == "auto":
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if api_key:
            model = selected_model or os.getenv("OPENROUTER_MODEL", "moonshotai/kimi-k2.5").strip() or "moonshotai/kimi-k2.5"
            app_name = os.getenv("OPENROUTER_APP_NAME", "hf-papers-archive").strip() or "hf-papers-archive"
            app_url = (
                os.getenv("OPENROUTER_APP_URL", "https://github.com/your-org/hf-papers-archive").strip()
                or "https://github.com/your-org/hf-papers-archive"
            )
            logging.info("Using OpenRouter translator (%s)", model)
            return OpenRouterTranslator(api_key=api_key, model=model, app_name=app_name, app_url=app_url)
        logging.info("Using dummy translator (no API key detected)")
        return DummyTranslator()

    return DummyTranslator()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def validate_date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date: {value}") from exc
    return value


def run(data_dir: Path, provider: str, force: bool, model: str, date: str) -> None:
    translator = choose_translator(provider, model_override=model)
    pattern = f"{date}__*.json" if date else "*.json"
    paper_files = sorted(data_dir.glob(pattern))
    if not paper_files:
        if date:
            logging.warning("No paper JSON files found in %s for date=%s", data_dir, date)
        else:
            logging.warning("No paper JSON files found in %s", data_dir)
        return

    translated = 0
    skipped = 0
    synthesized_en = 0

    for path in paper_files:
        paper = load_json(path)
        summary_en = normalize_text(str(paper.get("summary_en", "")))
        summary_zh = normalize_text(str(paper.get("summary_zh", "")))
        abstract = str(paper.get("abstract", ""))
        generated_summary_en = False

        if not summary_en and has_meaningful_abstract(abstract):
            try:
                generated = normalize_text(translator.summarize_abstract(abstract))
                if generated:
                    paper["summary_en"] = generated
                    summary_en = generated
                    generated_summary_en = True
                    synthesized_en += 1
                    logging.info("Synthesized summary_en from abstract for %s", path.name)
            except Exception as exc:  # noqa: BLE001
                logging.exception("Failed to synthesize summary_en for %s: %s", path.name, exc)

        if not summary_en:
            skipped += 1
            continue

        if summary_zh and not force and not generated_summary_en:
            skipped += 1
            continue

        try:
            paper["summary_zh"] = translator.translate(summary_en)
            dump_json(path, paper)
            translated += 1
            logging.info("Translated %s", path.name)
        except Exception as exc:  # noqa: BLE001
            logging.exception("Failed to translate %s: %s", path.name, exc)
            if generated_summary_en:
                dump_json(path, paper)
                logging.info("Saved synthesized summary_en only for %s", path.name)

    logging.info("Translation finished. translated=%d synthesized_en=%d skipped=%d", translated, synthesized_en, skipped)


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate summary_en -> summary_zh")
    parser.add_argument("--data-dir", type=Path, default=Path("data/papers"), help="Paper JSON folder")
    parser.add_argument(
        "--provider",
        default="auto",
        choices=["auto", "dummy", "openrouter"],
        help="Translation provider",
    )
    parser.add_argument(
        "--model",
        default="",
        help="Override model name (e.g., moonshotai/kimi-k2.5). Works for openrouter/auto.",
    )
    parser.add_argument("--force", action="store_true", help="Re-translate even when summary_zh exists")
    parser.add_argument("--date", type=validate_date, default="", help="Only process files for date YYYY-MM-DD")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    run(data_dir=args.data_dir, provider=args.provider, force=args.force, model=args.model, date=args.date)


if __name__ == "__main__":
    main()
