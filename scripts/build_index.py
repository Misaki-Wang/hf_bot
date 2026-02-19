#!/usr/bin/env python3
"""Build aggregate index files from per-paper JSON records."""

from __future__ import annotations

import argparse
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import re

import requests

ARXIV_ID_RE = re.compile(r"\b(\d{4}\.\d{4,5}(?:v\d+)?)\b", re.IGNORECASE)
DATE_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})__")
DAILY_OVERVIEW_SYSTEM_PROMPT = (
    "你是严谨的 AI 研究日报编辑。你必须严格遵循输出格式，禁止编造信息。"
)
AI_SUMMARY_LINE_RE = re.compile(r"(?im)^\s*-\s*Papers with AI Summary:\s*[^\n]*$")


def load_paper(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            logging.warning("Skip non-object JSON: %s", path)
            return None
        required = ["paper_id", "date", "title", "hf_url"]
        if any(not data.get(key) for key in required):
            logging.warning("Skip invalid paper file: %s", path)
            return None
        return data
    except Exception as exc:  # noqa: BLE001
        logging.warning("Skip unreadable file %s: %s", path, exc)
        return None


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def normalize_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def build_arxiv_pdf_url(arxiv_url: str) -> str:
    matched = ARXIV_ID_RE.search(arxiv_url or "")
    if not matched:
        return ""
    arxiv_id = matched.group(1)
    return f"https://arxiv.org/pdf/{arxiv_id}"


def extract_date_from_filename(path: Path | None) -> str:
    if path is None:
        return ""
    match = DATE_PREFIX_RE.match(path.stem)
    if not match:
        return ""
    return match.group(1)


def normalize_paper_record(raw: dict[str, Any], source_path: Path | None = None) -> dict[str, Any]:
    raw_date = str(raw.get("date", "")).strip()
    filename_date = extract_date_from_filename(source_path)
    record_date = filename_date or raw_date
    if filename_date and raw_date and filename_date != raw_date:
        logging.warning(
            "Date mismatch in %s: json=%s filename=%s; use filename date for display",
            source_path.name if source_path else "<unknown>",
            raw_date,
            filename_date,
        )

    arxiv_url = str(raw.get("arxiv_url", "")).strip()
    arxiv_pdf_url = str(raw.get("arxiv_pdf_url", "")).strip() or build_arxiv_pdf_url(arxiv_url)
    upvotes = raw.get("upvotes", 0)
    if isinstance(upvotes, str):
        upvotes = upvotes.replace(",", "").strip()
    try:
        upvotes_value = int(upvotes)
    except (TypeError, ValueError):
        upvotes_value = 0
    return {
        "date": record_date,
        "paper_id": str(raw.get("paper_id", "")).strip(),
        "title": str(raw.get("title", "")).strip(),
        "authors": normalize_str_list(raw.get("authors")),
        "abstract": str(raw.get("abstract", "")).strip(),
        "summary_en": str(raw.get("summary_en", "")).strip(),
        "summary_zh": str(raw.get("summary_zh", "")).strip(),
        "hf_url": str(raw.get("hf_url", "")).strip(),
        "arxiv_url": arxiv_url,
        "arxiv_pdf_url": arxiv_pdf_url,
        "github_url": str(raw.get("github_url", "")).strip(),
        "upvotes": upvotes_value,
        "fetched_at": str(raw.get("fetched_at", "")).strip(),
    }


def trim_text(value: str, limit: int) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def strip_ai_summary_metric(content: str) -> str:
    text = str(content or "")
    text = AI_SUMMARY_LINE_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_daily_summary_fallback(date: str, papers: list[dict[str, Any]]) -> str:
    if not papers:
        return strip_ai_summary_metric(
            (
            "Overview\n"
            f"- Date: {date}\n"
            "- Total Papers: 0\n"
            "- Total Upvotes: 0\n"
            "- Papers with GitHub: 0\n"
            "\n"
            "Key Takeaways\n"
            "1. No papers were fetched for this date.\n\n"
            "Notable Papers\n"
            "- N/A"
            )
        )

    total = len(papers)
    total_upvotes = sum(int(item.get("upvotes", 0)) for item in papers)
    with_code = sum(1 for item in papers if str(item.get("github_url", "")).strip())
    top = sorted(
        papers,
        key=lambda x: (int(x.get("upvotes", 0)), str(x.get("paper_id", ""))),
        reverse=True,
    )[:3]
    top_lines = []
    for item in top:
        title = trim_text(str(item.get("title", "")), 88)
        paper_id = str(item.get("paper_id", ""))
        upvotes = int(item.get("upvotes", 0))
        top_lines.append(f"- [{paper_id}] {title} (👍{upvotes})")

    return strip_ai_summary_metric(
        (
        "Overview\n"
        f"- Date: {date}\n"
        f"- Total Papers: {total}\n"
        f"- Total Upvotes: {total_upvotes}\n"
        f"- Papers with GitHub: {with_code}\n"
        "\n"
        "Key Takeaways\n"
        f"1. {date} has {total} papers with broad coverage across multiple AI subfields.\n"
        f"2. Community attention is concentrated on a few papers (total 👍 {total_upvotes}).\n"
        f"3. {with_code} papers provide GitHub links, indicating practical reproducibility focus.\n\n"
        "Notable Papers\n"
        + "\n".join(top_lines)
        )
    )


def build_daily_summary_prompt(date: str, papers: list[dict[str, Any]]) -> str:
    total = len(papers)
    total_upvotes = sum(int(item.get("upvotes", 0)) for item in papers)
    with_code = sum(1 for item in papers if str(item.get("github_url", "")).strip())
    ranked = sorted(
        papers,
        key=lambda x: (int(x.get("upvotes", 0)), str(x.get("paper_id", ""))),
        reverse=True,
    )[:10]
    lines: list[str] = []
    for item in ranked:
        paper_id = str(item.get("paper_id", ""))
        title = trim_text(str(item.get("title", "")), 140)
        upvotes = int(item.get("upvotes", 0))
        summary_en = trim_text(str(item.get("summary_en", "")), 160)
        abstract = trim_text(str(item.get("abstract", "")), 160)
        gist = summary_en or abstract
        lines.append(f"- [{paper_id}] {title} | upvotes={upvotes} | gist={gist}")

    context = "\n".join(lines)
    return (
        "任务：基于给定论文列表生成用于网页展示的中文日度总览。\n"
        "输出要求：必须是纯文本，严格按模板，禁止额外段落。\n\n"
        "模板（字段名和顺序不可修改）：\n"
        "Overview\n"
        "- Date: <YYYY-MM-DD>\n"
        "- Total Papers: <number>\n"
        "- Total Upvotes: <number>\n"
        "- Papers with GitHub: <number>\n"
        "\n"
        "Key Takeaways\n"
        "1. <一句话，总体趋势>\n"
        "2. <一句话，总体趋势>\n"
        "3. <一句话，总体趋势>\n"
        "4. <一句话，总体趋势>\n\n"
        "Notable Papers\n"
        "- [paper_id] <title> (👍<upvotes>): <一句话亮点>\n"
        "- [paper_id] <title> (👍<upvotes>): <一句话亮点>\n"
        "- [paper_id] <title> (👍<upvotes>): <一句话亮点>\n"
        "- [paper_id] <title> (👍<upvotes>): <一句话亮点>\n"
        "- [paper_id] <title> (👍<upvotes>): <一句话亮点>\n\n"
        "约束：\n"
        "1) 仅使用给定条目与统计信息，不得编造论文、数字或结论。\n"
        "2) Key Takeaways 必须恰好 4 条；Notable Papers 必须恰好 5 条。\n"
        "3) 优先覆盖 upvotes 高、信息密度高、主题代表性强的论文。\n"
        "4) 保留关键英文术语、模型名、数据集名和缩写（如 RLHF、VLM、Diffusion）。\n"
        "5) 语言客观、简洁，避免营销化表达。\n"
        "6) 若某信息缺失，请明确写“信息不足”，不要猜测。\n\n"
        f"统计信息（可直接使用）:\n"
        f"- Date: {date}\n"
        f"- Total Papers: {total}\n"
        f"- Total Upvotes: {total_upvotes}\n"
        f"- Papers with GitHub: {with_code}\n"
        "\n"
        f"论文条目:\n{context}\n"
    )


def generate_daily_summary_openrouter(date: str, papers: list[dict[str, Any]]) -> tuple[str, str]:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    model = os.getenv("OPENROUTER_SUMMARY_MODEL", "").strip() or os.getenv("OPENROUTER_MODEL", "").strip() or "moonshotai/kimi-k2.5"
    app_name = os.getenv("OPENROUTER_APP_NAME", "hf-papers-archive").strip() or "hf-papers-archive"
    app_url = (
        os.getenv("OPENROUTER_APP_URL", "https://github.com/your-org/hf-papers-archive").strip()
        or "https://github.com/your-org/hf-papers-archive"
    )

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": DAILY_OVERVIEW_SYSTEM_PROMPT,
            },
            {"role": "user", "content": build_daily_summary_prompt(date, papers)},
        ],
        "temperature": 0.1,
        "stream": False,
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": app_url,
            "X-Title": app_name,
        },
        json=payload,
        timeout=45,
    )
    response.raise_for_status()
    body = response.json()
    choices = body.get("choices", [])
    if not choices:
        raise RuntimeError("OpenRouter summary response has no choices")
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = str(item.get("text", "")).strip()
                if text:
                    parts.append(text)
        summary = "\n".join(parts).strip()
    else:
        summary = str(content).strip()

    if not summary:
        raise RuntimeError("OpenRouter summary content is empty")
    return strip_ai_summary_metric(summary), model


def generate_daily_summary(date: str, papers: list[dict[str, Any]]) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    try:
        summary, model = generate_daily_summary_openrouter(date, papers)
        return {
            "date": date,
            "content": summary,
            "source": "openrouter",
            "model": model,
            "generated_at": generated_at,
        }
    except Exception as exc:  # noqa: BLE001
        logging.warning("Daily summary AI generation failed, fallback to local summary: %s", exc)
        return {
            "date": date,
            "content": build_daily_summary_fallback(date, papers),
            "source": "fallback",
            "model": "",
            "generated_at": generated_at,
        }


def build_fallback_daily_summary(date: str, papers: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "date": date,
        "content": build_daily_summary_fallback(date, papers),
        "source": "fallback",
        "model": "",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def normalize_existing_daily_summary(date: str, raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    content = strip_ai_summary_metric(str(raw.get("content", "")))
    if not content:
        return None
    return {
        "date": date,
        "content": content,
        "source": str(raw.get("source", "fallback")).strip() or "fallback",
        "model": str(raw.get("model", "")).strip(),
        "generated_at": str(raw.get("generated_at", "")).strip() or datetime.now(timezone.utc).isoformat(),
    }


def load_existing_daily_summaries(index_path: Path) -> dict[str, dict[str, Any]]:
    if not index_path.exists():
        return {}

    try:
        with index_path.open("r", encoding="utf-8") as fh:
            existing = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        logging.warning("Failed to read existing index for daily summaries: %s", exc)
        return {}

    if not isinstance(existing, dict):
        return {}

    out: dict[str, dict[str, Any]] = {}

    raw_map = existing.get("daily_summaries")
    if isinstance(raw_map, dict):
        for raw_date, raw_summary in raw_map.items():
            date = str(raw_date).strip()
            if not date:
                continue
            normalized = normalize_existing_daily_summary(date, raw_summary)
            if normalized:
                out[date] = normalized

    raw_single = existing.get("daily_summary")
    if isinstance(raw_single, dict):
        single_date = str(raw_single.get("date", "")).strip()
        if single_date and single_date not in out:
            normalized = normalize_existing_daily_summary(single_date, raw_single)
            if normalized:
                out[single_date] = normalized

    return out


def run(papers_dir: Path, out_dir: Path) -> None:
    paper_files = sorted(papers_dir.glob("*.json"))
    papers: list[dict[str, Any]] = []

    for file in paper_files:
        paper = load_paper(file)
        if not paper:
            continue

        papers.append(normalize_paper_record(paper, source_path=file))

    papers.sort(
        key=lambda x: (
            str(x.get("date", "")),
            int(x.get("upvotes", 0)),
            str(x.get("paper_id", "")),
        ),
        reverse=True,
    )

    dates_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for paper in papers:
        dates_map[str(paper["date"])].append(paper)

    date_keys = sorted(dates_map.keys(), reverse=True)
    existing_summaries = load_existing_daily_summaries(out_dir / "index.json")
    daily_summary: dict[str, Any] | None = None
    daily_summaries: dict[str, dict[str, Any]] = {}
    reused_count = 0
    generated_count = 0
    fallback_count = 0
    if date_keys:
        latest_date = date_keys[0]
        for date in date_keys:
            existing_summary = existing_summaries.get(date)
            if existing_summary:
                daily_summaries[date] = existing_summary
                reused_count += 1
                continue

            if date == latest_date:
                daily_summaries[date] = generate_daily_summary(date, dates_map[date])
                generated_count += 1
            else:
                daily_summaries[date] = build_fallback_daily_summary(date, dates_map[date])
                fallback_count += 1

        daily_summary = daily_summaries.get(latest_date)

    index = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(papers),
        "dates": date_keys,
        "daily_summary": daily_summary,
        "daily_summaries": daily_summaries,
        "papers": papers,
    }
    write_json(out_dir / "index.json", index)

    search_docs = []
    for paper in papers:
        search_docs.append(
            {
                "id": str(paper.get("paper_id", "")),
                "date": str(paper.get("date", "")),
                "title": str(paper.get("title", "")),
                "authors": " ".join(normalize_str_list(paper.get("authors"))),
                "abstract": str(paper.get("abstract", "")),
                "summary_en": str(paper.get("summary_en", "")),
                "summary_zh": str(paper.get("summary_zh", "")),
                "upvotes": int(paper.get("upvotes", 0)),
            }
        )
    write_json(out_dir / "search_index.json", search_docs)

    dates_dir = out_dir / "dates"
    for date in date_keys:
        write_json(
            dates_dir / f"{date}.json",
            {
                "date": date,
                "count": len(dates_map[date]),
                "papers": dates_map[date],
            },
        )

    logging.info(
        "Built index files: papers=%d dates=%d summaries(reused=%d generated=%d fallback=%d)",
        len(papers),
        len(date_keys),
        reused_count,
        generated_count,
        fallback_count,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build aggregate JSON index for site")
    parser.add_argument("--papers-dir", type=Path, default=Path("data/papers"))
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    run(papers_dir=args.papers_dir, out_dir=args.out_dir)


if __name__ == "__main__":
    main()
