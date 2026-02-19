#!/usr/bin/env python3
"""Translate summary_en into summary_zh for archived paper JSON files."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
import random
import re
import threading
import time
from dataclasses import dataclass, field
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
DEFAULT_TRANSLATE_WORKERS = 6
MAX_TRANSLATE_WORKERS = 12
PROMPT_LANG_CHOICES = ("auto", "zh", "en")

SUMMARY_PROMPTS = {
    "zh": {
        "system": "你是一名严谨的 AI 论文编辑。请基于论文摘要产出忠实、精炼的英文总结。",
        "user": (
            "请将下面的 abstract 总结为 2-4 句英文。\n"
            "要求：\n"
            "- 覆盖问题、方法、关键结果或论文声称的收益。\n"
            "- 保留术语、模型名、数据集名、指标、数字和缩写。\n"
            "- 不要使用 markdown、不要分点、不要夸张、不要猜测。\n"
            "- 若原文未明确给出结果，不要编造。\n"
            "- 只输出英文总结正文。\n\n"
            "Abstract:\n{abstract}"
        ),
    },
    "en": {
        "system": "You are a rigorous AI paper editor. Create a faithful and concise English summary from the abstract.",
        "user": (
            "Summarize the following abstract in 2-4 English sentences.\n"
            "Requirements:\n"
            "- Cover the problem, method, and key result/claimed benefit.\n"
            "- Keep technical terms, model names, datasets, metrics, numbers, and acronyms.\n"
            "- No markdown, no bullet points, no hype, no guessing.\n"
            "- If a result is not explicitly stated, do not invent one.\n"
            "- Output only the English summary text.\n\n"
            "Abstract:\n{abstract}"
        ),
    },
}

TRANSLATE_PROMPTS = {
    "zh": {
        "system": "你是一名专业的 AI 论文翻译，负责将英文内容翻译为简体中文。",
        "user": (
            "请将下面的英文 summary 翻译成简体中文。\n"
            "要求：\n"
            "- 尽量保留术语、模型名、数据集名、指标、数字和缩写。\n"
            "- 语义完整准确，不增删事实。\n"
            "- 语气简洁中性，避免口语化和营销表达。\n"
            "- 只输出中文译文，不要解释，不要 markdown。\n\n"
            "English summary:\n{summary}"
        ),
    },
    "en": {
        "system": "You are an expert AI paper translator. Translate English content into Simplified Chinese.",
        "user": (
            "Translate the following English summary into Simplified Chinese.\n"
            "Requirements:\n"
            "- Preserve technical terms, model names, datasets, metrics, numbers, and acronyms when possible.\n"
            "- Keep facts fully accurate; do not add or remove claims.\n"
            "- Use concise, neutral style.\n"
            "- Output only the Chinese translation text. No explanation, no markdown.\n\n"
            "English summary:\n{summary}"
        ),
    },
}


def normalize_prompt_lang(value: str | None) -> str:
    cleaned = (value or "auto").strip().lower()
    if cleaned in PROMPT_LANG_CHOICES:
        return cleaned
    return "auto"


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
    prompt_lang: str = "auto"
    timeout: float = 30.0
    max_attempts: int = 4
    max_connections: int = 12
    endpoint: str = "https://openrouter.ai/api/v1/chat/completions"
    app_name: str = "hf-papers-archive"
    app_url: str = "https://github.com/your-org/hf-papers-archive"
    _thread_local: threading.local = field(default_factory=threading.local, init=False, repr=False)

    def _session(self) -> requests.Session:
        session = getattr(self._thread_local, "session", None)
        if isinstance(session, requests.Session):
            return session

        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=self.max_connections,
            pool_maxsize=self.max_connections,
            max_retries=0,
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": self.app_url,
                "X-Title": self.app_name,
            }
        )
        self._thread_local.session = session
        return session

    def _compute_retry_wait(self, attempt: int, response: requests.Response | None = None) -> float:
        retry_after_s = 0.0
        if response is not None:
            retry_after_raw = (response.headers.get("Retry-After") or "").strip()
            if retry_after_raw:
                try:
                    retry_after_s = max(0.0, float(retry_after_raw))
                except ValueError:
                    retry_after_s = 0.0
        backoff = min(8.0, 0.8 * (2 ** (attempt - 1)))
        jitter = random.uniform(0.05, 0.45)
        return max(retry_after_s, backoff + jitter)

    def _chat(self, messages: list[dict[str, str]], temperature: float) -> str:
        payload = {"model": self.model, "messages": messages, "temperature": temperature, "stream": False}
        last_error: Exception | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self._session().post(
                    self.endpoint,
                    json=payload,
                    timeout=self.timeout,
                )
                if response.status_code in (429, 500, 502, 503, 504):
                    wait_s = self._compute_retry_wait(attempt, response)
                    last_error = RuntimeError(f"OpenRouter HTTP {response.status_code}")
                    if attempt < self.max_attempts:
                        time.sleep(wait_s)
                        continue
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
                if attempt < self.max_attempts:
                    time.sleep(self._compute_retry_wait(attempt))
                    continue
        raise RuntimeError(f"OpenRouter request failed after retries: {last_error}")

    def _resolve_task_prompt_lang(self, task: str) -> str:
        lang = normalize_prompt_lang(self.prompt_lang)
        if lang in ("zh", "en"):
            return lang
        if task == "summarize":
            return "en"
        return "zh"

    def summarize_abstract(self, text: str) -> str:
        content = normalize_text(text)
        if not content:
            return ""
        prompt_lang = self._resolve_task_prompt_lang("summarize")
        prompt = SUMMARY_PROMPTS[prompt_lang]
        return self._chat(
            messages=[
                {
                    "role": "system",
                    "content": prompt["system"],
                },
                {
                    "role": "user",
                    "content": prompt["user"].format(abstract=content),
                },
            ],
            temperature=0.15,
        )

    def translate(self, text: str) -> str:
        content = normalize_text(text)
        if not content:
            return ""
        prompt_lang = self._resolve_task_prompt_lang("translate")
        prompt = TRANSLATE_PROMPTS[prompt_lang]
        return self._chat(
            messages=[
                {
                    "role": "system",
                    "content": prompt["system"],
                },
                {
                    "role": "user",
                    "content": prompt["user"].format(summary=content),
                },
            ],
            temperature=0.05,
        )


def choose_translator(
    provider: str,
    model_override: str = "",
    concurrency_hint: int = DEFAULT_TRANSLATE_WORKERS,
    prompt_lang: str = "auto",
) -> Translator:
    provider = provider.lower()
    selected_model = model_override.strip()
    pool_size = max(8, min(32, concurrency_hint * 2))
    selected_prompt_lang = normalize_prompt_lang(prompt_lang)
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
        return OpenRouterTranslator(
            api_key=api_key,
            model=model,
            prompt_lang=selected_prompt_lang,
            app_name=app_name,
            app_url=app_url,
            max_connections=pool_size,
        )

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
            return OpenRouterTranslator(
                api_key=api_key,
                model=model,
                prompt_lang=selected_prompt_lang,
                app_name=app_name,
                app_url=app_url,
                max_connections=pool_size,
            )
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


def collect_paper_files(data_dir: Path, date: str | None) -> list[Path]:
    if date:
        by_dir = sorted((data_dir / date).glob("*.json"))
        legacy = sorted(data_dir.glob(f"{date}__*.json"))
        merged = by_dir + [path for path in legacy if path not in by_dir]
        return merged
    return sorted(data_dir.rglob("*.json"))


@dataclass
class ProcessStats:
    translated: int = 0
    skipped: int = 0
    synthesized_en: int = 0
    failed: int = 0

    def add(self, other: ProcessStats) -> None:
        self.translated += other.translated
        self.skipped += other.skipped
        self.synthesized_en += other.synthesized_en
        self.failed += other.failed


def process_paper_file(path: Path, translator: Translator, force: bool) -> ProcessStats:
    stats = ProcessStats()
    try:
        paper = load_json(path)
    except Exception as exc:  # noqa: BLE001
        logging.exception("Failed to read %s: %s", path.name, exc)
        stats.failed += 1
        return stats

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
                stats.synthesized_en += 1
                logging.info("Synthesized summary_en from abstract for %s", path.name)
        except Exception as exc:  # noqa: BLE001
            stats.failed += 1
            logging.exception("Failed to synthesize summary_en for %s: %s", path.name, exc)

    if not summary_en:
        stats.skipped += 1
        return stats

    if summary_zh and not force and not generated_summary_en:
        stats.skipped += 1
        return stats

    try:
        paper["summary_zh"] = translator.translate(summary_en)
        dump_json(path, paper)
        stats.translated += 1
        logging.info("Translated %s", path.name)
    except Exception as exc:  # noqa: BLE001
        stats.failed += 1
        logging.exception("Failed to translate %s: %s", path.name, exc)
        if generated_summary_en:
            try:
                dump_json(path, paper)
                logging.info("Saved synthesized summary_en only for %s", path.name)
            except Exception as dump_exc:  # noqa: BLE001
                stats.failed += 1
                logging.exception("Failed to persist synthesized summary_en for %s: %s", path.name, dump_exc)

    return stats


def run(
    data_dir: Path,
    provider: str,
    force: bool,
    model: str,
    prompt_lang: str,
    date: str | None,
    workers: int,
) -> None:
    requested_workers = max(1, min(workers, MAX_TRANSLATE_WORKERS))
    if requested_workers != workers:
        logging.warning("Requested workers=%d adjusted to safe limit=%d", workers, requested_workers)

    selected_prompt_lang = normalize_prompt_lang(prompt_lang)
    translator = choose_translator(
        provider,
        model_override=model,
        concurrency_hint=requested_workers,
        prompt_lang=selected_prompt_lang,
    )
    if isinstance(translator, OpenRouterTranslator):
        if selected_prompt_lang == "auto":
            logging.info("Prompt language mode=auto (summarize: en, translate: zh)")
        else:
            logging.info("Prompt language mode=%s (forced)", selected_prompt_lang)

    paper_files = collect_paper_files(data_dir, date)
    if not paper_files:
        if date:
            logging.warning("No paper JSON files found in %s for date=%s", data_dir, date)
        else:
            logging.warning("No paper JSON files found in %s", data_dir)
        return

    target_workers = requested_workers
    if isinstance(translator, DummyTranslator):
        target_workers = 1
    target_workers = min(target_workers, len(paper_files))
    logging.info("Translation workers: %d", target_workers)

    totals = ProcessStats()
    if target_workers == 1:
        for path in paper_files:
            totals.add(process_paper_file(path, translator, force))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=target_workers) as executor:
            future_map = {
                executor.submit(process_paper_file, path, translator, force): path
                for path in paper_files
            }
            for future in concurrent.futures.as_completed(future_map):
                path = future_map[future]
                try:
                    totals.add(future.result())
                except Exception as exc:  # noqa: BLE001
                    totals.failed += 1
                    logging.exception("Unhandled worker error for %s: %s", path.name, exc)

    logging.info(
        "Translation finished. translated=%d synthesized_en=%d skipped=%d failed=%d",
        totals.translated,
        totals.synthesized_en,
        totals.skipped,
        totals.failed,
    )


def main() -> None:
    default_workers_raw = (
        os.getenv("TRANSLATE_WORKERS", str(DEFAULT_TRANSLATE_WORKERS)).strip()
        or str(DEFAULT_TRANSLATE_WORKERS)
    )
    default_prompt_lang = normalize_prompt_lang(
        os.getenv("TRANSLATE_PROMPT_LANG", os.getenv("OPENROUTER_PROMPT_LANG", "auto"))
    )
    try:
        default_workers = max(1, int(default_workers_raw))
    except ValueError:
        default_workers = DEFAULT_TRANSLATE_WORKERS

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
    parser.add_argument(
        "--prompt-lang",
        default=default_prompt_lang,
        choices=PROMPT_LANG_CHOICES,
        help=(
            "Prompt language mode: auto/zh/en. "
            "auto = summarize prompt in English + translate prompt in Chinese."
        ),
    )
    parser.add_argument("--force", action="store_true", help="Re-translate even when summary_zh exists")
    parser.add_argument("--date", type=validate_date, default=None, help="Only process files for date YYYY-MM-DD")
    parser.add_argument(
        "--workers",
        type=int,
        default=default_workers,
        help=(
            f"Max concurrent paper translation jobs "
            f"(default: env TRANSLATE_WORKERS or {DEFAULT_TRANSLATE_WORKERS}; "
            f"capped at {MAX_TRANSLATE_WORKERS})"
        ),
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    args = parser.parse_args()
    if args.workers < 1:
        raise SystemExit("--workers must be >= 1")

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    run(
        data_dir=args.data_dir,
        provider=args.provider,
        force=args.force,
        model=args.model,
        prompt_lang=args.prompt_lang,
        date=args.date,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
