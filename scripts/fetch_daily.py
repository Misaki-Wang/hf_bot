#!/usr/bin/env python3
"""Fetch Hugging Face papers for a given date and archive each paper as JSON."""

from __future__ import annotations

import argparse
import html
import json
import logging
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

HF_BASE_URL = "https://huggingface.co"
HF_DATE_URL_TMPL = "https://huggingface.co/papers/date/{date}"
ARXIV_ABS_URL_TMPL = "https://arxiv.org/abs/{arxiv_id}"

ARXIV_ID_RE = re.compile(r"\b(\d{4}\.\d{4,5}(?:v\d+)?)\b", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(r"^\$[0-9a-zA-Z]+$")


@dataclass
class PaperRecord:
    date: str
    paper_id: str
    title: str
    authors: list[str]
    abstract: str
    summary_en: str
    summary_zh: str
    hf_url: str
    arxiv_url: str
    arxiv_pdf_url: str
    github_url: str
    upvotes: int
    fetched_at: str

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "paper_id": self.paper_id,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "summary_en": self.summary_en,
            "summary_zh": self.summary_zh,
            "hf_url": self.hf_url,
            "arxiv_url": self.arxiv_url,
            "arxiv_pdf_url": self.arxiv_pdf_url,
            "github_url": self.github_url,
            "upvotes": self.upvotes,
            "fetched_at": self.fetched_at,
        }


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "hf-papers-archive-bot/1.0 "
                "(+https://github.com/your-org/hf-papers-archive)"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return session


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = text.strip("\u200b\ufeff")
    return text


def dedupe_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for raw in items:
        item = clean_text(raw)
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def to_int(value: object, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = clean_text(value).replace(",", "")
        if text.isdigit():
            return int(text)
    return default


def parse_hydrater_props(soup: BeautifulSoup, target: str) -> dict:
    selector = f"[data-target='{target}'][data-props]"
    for node in soup.select(selector):
        raw = str(node.get("data-props") or "")
        if not raw:
            continue
        decoded = html.unescape(raw)
        try:
            data = json.loads(decoded)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return {}


def extract_paper_payload(soup: BeautifulSoup) -> dict:
    props = parse_hydrater_props(soup, "PaperContent")
    paper = props.get("paper")
    if isinstance(paper, dict):
        return paper
    return {}


def extract_github_url(soup: BeautifulSoup, paper_payload: dict) -> str:
    candidate = clean_text(str(paper_payload.get("githubRepo", "")))
    if candidate.startswith("http") and "github.com/" in candidate:
        return candidate

    for link in soup.select("a[href*='github.com/']"):
        href = clean_text(str(link.get("href") or ""))
        if not href.startswith("http"):
            continue
        text = clean_text(link.get_text(" ", strip=True)).casefold()
        classes = " ".join(link.get("class") or []).casefold()
        if "github" in text or "btn" in classes:
            return href
    return ""


def extract_upvotes(soup: BeautifulSoup, paper_payload: dict) -> int:
    upvotes = to_int(paper_payload.get("upvotes"), default=0)
    if upvotes > 0:
        return upvotes

    control_props = parse_hydrater_props(soup, "UpvoteControl")
    upvotes = to_int(control_props.get("upvotes"), default=0)
    if upvotes > 0:
        return upvotes

    for link in soup.select("a[href*='/login?next=%2Fpapers%2F']"):
        text = clean_text(link.get_text(" ", strip=True))
        match = re.search(r"\bupvote\b\s*([0-9][0-9,]*)", text, flags=re.IGNORECASE)
        if not match:
            continue
        return to_int(match.group(1), default=0)

    return 0


def fetch_html(
    session: requests.Session,
    url: str,
    max_attempts: int = 3,
    timeout: float = 25.0,
) -> str:
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = session.get(url, timeout=timeout)
            if response.status_code >= 500:
                raise requests.HTTPError(f"{response.status_code} for {url}")
            response.raise_for_status()
            return response.text
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == max_attempts:
                break
            wait_s = min(5.0, 0.8 * attempt + random.uniform(0.1, 0.9))
            logging.warning(
                "Fetch failed (%s/%s) for %s: %s; retry in %.2fs",
                attempt,
                max_attempts,
                url,
                exc,
                wait_s,
            )
            time.sleep(wait_s)
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def parse_paper_urls_from_date_page(date_html: str) -> list[str]:
    soup = BeautifulSoup(date_html, "lxml")
    urls: set[str] = set()
    excluded_slugs = {
        "date",
        "trending",
        "daily",
        "weekly",
        "monthly",
        "search",
        "about",
    }
    for link in soup.select("a[href^='/papers/']"):
        href = (link.get("href") or "").strip()
        if not href:
            continue
        abs_url = urljoin(HF_BASE_URL, href)
        parsed = urlparse(abs_url)
        match = re.match(r"^/papers/([^/?#]+)$", parsed.path)
        if not match:
            continue
        paper_id = match.group(1)
        if paper_id.lower() in excluded_slugs:
            continue
        # Skip site-level nav links that are not real paper ids.
        if not re.search(r"\d", paper_id):
            continue
        urls.add(urljoin(HF_BASE_URL, parsed.path))
    return sorted(urls)


def parse_jsonld_authors(soup: BeautifulSoup) -> list[str]:
    author_names: list[str] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = clean_text(script.get_text())
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        blobs = data if isinstance(data, list) else [data]
        for blob in blobs:
            if not isinstance(blob, dict):
                continue
            authors = blob.get("author")
            if isinstance(authors, list):
                for item in authors:
                    if isinstance(item, dict) and item.get("name"):
                        author_names.append(str(item["name"]))
                    elif isinstance(item, str):
                        author_names.append(item)
            elif isinstance(authors, dict) and authors.get("name"):
                author_names.append(str(authors["name"]))
            elif isinstance(authors, str):
                author_names.append(authors)
    return dedupe_keep_order(normalize_author_name(name) for name in author_names)


def normalize_title(text: str) -> str:
    cleaned = clean_text(text).replace(" - Hugging Face", "").strip()
    cleaned = re.sub(r"^paper page\s*-\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def normalize_author_name(name: str) -> str:
    cleaned = clean_text(name)
    cleaned = cleaned.strip(" ,;|")
    return cleaned


def split_author_blob(text: str) -> list[str]:
    raw = clean_text(text)
    if not raw:
        return []
    if ",," in raw:
        parts = re.split(r"\s*,\s*,+\s*", raw)
        return [normalize_author_name(part) for part in parts if normalize_author_name(part)]
    return [normalize_author_name(raw)]


def extract_title(soup: BeautifulSoup) -> str:
    selectors = [
        ("meta", {"property": "og:title"}, "content"),
        ("meta", {"name": "twitter:title"}, "content"),
    ]
    for tag_name, attrs, key in selectors:
        tag = soup.find(tag_name, attrs=attrs)
        if tag and tag.get(key):
            text = normalize_title(str(tag.get(key)))
            if text:
                return text
    h1 = soup.find("h1")
    if h1:
        text = normalize_title(h1.get_text(" ", strip=True))
        if text:
            return text
    if soup.title and soup.title.string:
        text = normalize_title(soup.title.string)
        return text
    return ""


def extract_authors(soup: BeautifulSoup) -> list[str]:
    names = parse_jsonld_authors(soup)
    if names:
        return names

    candidates: list[str] = []
    selectors = [
        "a[href*='author']",
        "a[href*='papers?author=']",
        "[data-testid*='author']",
        ".author",
    ]
    for selector in selectors:
        for node in soup.select(selector):
            text = clean_text(node.get_text(" ", strip=True))
            if text and 1 <= len(text) <= 80:
                candidates.append(text)

    if not candidates:
        for heading in soup.find_all(re.compile("^h[1-6]$")):
            head_text = clean_text(heading.get_text(" ", strip=True)).lower()
            if "author" not in head_text:
                continue
            for nxt in heading.find_all_next():
                if nxt.name and re.match(r"^h[1-6]$", nxt.name):
                    break
                if nxt.name in {"a", "li", "span", "p"}:
                    text = clean_text(nxt.get_text(" ", strip=True))
                    if text and len(text) <= 80:
                        candidates.append(text)
                if len(candidates) > 32:
                    break
            if candidates:
                break

    cleaned: list[str] = []
    for candidate in dedupe_keep_order(candidates):
        for name in split_author_blob(candidate):
            low = name.casefold()
            if low in {"authors", "author", "read paper", "paper"}:
                continue
            if re.search(r"\b(like|comment|share)\b", low):
                continue
            if len(name.split()) > 8:
                continue
            cleaned.append(name)
    return dedupe_keep_order(cleaned)


def extract_summary_en(soup: BeautifulSoup, paper_payload: dict | None = None) -> str:
    marker_pattern = re.compile(r"ai-generated summary", re.IGNORECASE)
    noise_pattern = re.compile(r"\b(join|discussion|comment|share|like|report)\b", re.IGNORECASE)
    payload = paper_payload or {}

    payload_summary = clean_text(str(payload.get("ai_summary", "")))
    if payload_summary and len(payload_summary) >= 40 and not noise_pattern.search(payload_summary):
        return payload_summary

    # Prefer the explicit summary box rendered above the Abstract paragraph.
    abstract_heading = soup.find(re.compile("^h[1-6]$"), string=lambda s: s and clean_text(s).casefold() == "abstract")
    if abstract_heading and isinstance(abstract_heading, Tag):
        abstract_container = abstract_heading.find_next_sibling("div")
        if abstract_container and isinstance(abstract_container, Tag):
            for marker in abstract_container.find_all(string=marker_pattern):
                marker_parent = marker.parent if marker else None
                if not isinstance(marker_parent, Tag):
                    continue
                summary_box = marker_parent.parent if isinstance(marker_parent.parent, Tag) else marker_parent
                raw_text = clean_text(summary_box.get_text(" ", strip=True))
                cleaned = marker_pattern.sub("", raw_text).strip(" :-")
                if cleaned and len(cleaned) >= 40 and not noise_pattern.search(cleaned):
                    return cleaned

    # Prefer extracting around explicit "AI-generated summary" marker.
    for marker in soup.find_all(string=marker_pattern):
        if not marker or not marker.parent:
            continue
        parent = marker.parent
        ancestors = [parent]
        ancestors.extend(parent.parents)
        for ancestor in ancestors[:8]:
            if not isinstance(ancestor, Tag):
                continue
            if ancestor.name not in {"div", "section", "article", "main"}:
                continue
            candidates: list[str] = []
            for node in ancestor.find_all(["p", "li"]):
                text = clean_text(node.get_text(" ", strip=True))
                if not text or len(text) < 60:
                    continue
                if marker_pattern.search(text):
                    continue
                if noise_pattern.search(text):
                    continue
                candidates.append(text)
            candidates = dedupe_keep_order(candidates)
            if not candidates:
                continue
            best = max(candidates, key=len)
            if len(best) >= 80:
                return best

    # Fallback: previous heading-based approach.
    for heading in soup.find_all(re.compile("^h[1-6]$")):
        head_text = clean_text(heading.get_text(" ", strip=True))
        if "ai-generated summary" not in head_text.lower():
            continue

        chunks: list[str] = []
        for nxt in heading.find_all_next():
            if nxt is heading:
                continue
            if nxt.name and re.match(r"^h[1-6]$", nxt.name):
                break
            if nxt.name in {"p", "li", "div"}:
                text = clean_text(nxt.get_text(" ", strip=True))
                if text and len(text) > 30:
                    chunks.append(text)
            if len(" ".join(chunks)) > 2400:
                break
        if chunks:
            return clean_text(" ".join(dedupe_keep_order(chunks)))

    # Last resort: meta description (only when it looks like a real summary).
    for meta in (
        soup.find("meta", attrs={"name": "description"}),
        soup.find("meta", attrs={"property": "og:description"}),
    ):
        if meta and meta.get("content"):
            text = clean_text(str(meta.get("content")))
            if text and not noise_pattern.search(text) and len(text) >= 40:
                return text
    return ""


def extract_abstract(soup: BeautifulSoup) -> str:
    marker_pattern = re.compile(r"ai-generated summary", re.IGNORECASE)
    noise_pattern = re.compile(r"\b(join|discussion|comment|share|like|report|view pdf)\b", re.IGNORECASE)

    for heading in soup.find_all(re.compile("^h[1-6]$")):
        head_text = clean_text(heading.get_text(" ", strip=True))
        if head_text.casefold() != "abstract":
            continue

        # Prefer paragraph nodes inside the Abstract container.
        sibling = heading.find_next_sibling("div")
        if sibling and isinstance(sibling, Tag):
            paragraph_chunks: list[str] = []
            for node in sibling.find_all("p"):
                text = clean_text(node.get_text(" ", strip=True))
                if not text or len(text) < 60:
                    continue
                if marker_pattern.search(text):
                    continue
                if noise_pattern.search(text):
                    continue
                paragraph_chunks.append(text)
            paragraph_chunks = dedupe_keep_order(paragraph_chunks)
            if paragraph_chunks:
                return clean_text(" ".join(paragraph_chunks))

        chunks: list[str] = []
        for nxt in heading.find_all_next():
            if nxt is heading:
                continue
            if nxt.name and re.match(r"^h[1-6]$", nxt.name):
                break
            if nxt.name in {"p", "li"}:
                text = clean_text(nxt.get_text(" ", strip=True))
                if not text or len(text) < 60:
                    continue
                if marker_pattern.search(text):
                    continue
                if noise_pattern.search(text):
                    continue
                chunks.append(text)
            if len(" ".join(chunks)) > 5000:
                break
        if chunks:
            return clean_text(" ".join(dedupe_keep_order(chunks)))

    return ""


def find_arxiv_url(soup: BeautifulSoup, paper_id: str) -> str:
    for link in soup.select("a[href]"):
        href = clean_text(str(link.get("href") or ""))
        if "arxiv.org" not in href:
            continue
        if "/pdf/" in href:
            href = re.sub(r"/pdf/(.+?)\.pdf", r"/abs/\1", href)
        return href

    if ARXIV_ID_RE.search(paper_id):
        arxiv_id = ARXIV_ID_RE.search(paper_id).group(1)  # type: ignore[union-attr]
        return ARXIV_ABS_URL_TMPL.format(arxiv_id=arxiv_id)
    return ""


def build_arxiv_pdf_url(arxiv_url: str) -> str:
    matched = ARXIV_ID_RE.search(arxiv_url or "")
    if not matched:
        return ""
    arxiv_id = matched.group(1)
    return f"https://arxiv.org/pdf/{arxiv_id}"


def output_path_for_paper(output_dir: Path, date: str, paper_id: str) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9._-]", "_", paper_id)
    return output_dir / f"{date}__{safe_id}.json"


def has_meaningful_text(value: object, min_len: int = 48) -> bool:
    text = clean_text(str(value or ""))
    if not text:
        return False
    if PLACEHOLDER_RE.match(text):
        return False
    return len(text) >= min_len


def is_complete_existing_json(path: Path, *, date: str, paper_id: str, hf_url: str) -> bool:
    if not path.exists():
        return False
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return False
    if not isinstance(raw, dict):
        return False

    if clean_text(str(raw.get("date", ""))) != date:
        return False
    if clean_text(str(raw.get("paper_id", ""))) != paper_id:
        return False
    if clean_text(str(raw.get("hf_url", ""))) != hf_url:
        return False
    if not clean_text(str(raw.get("title", ""))):
        return False
    if not isinstance(raw.get("authors"), list) or not raw.get("authors"):
        return False
    if not clean_text(str(raw.get("fetched_at", ""))):
        return False

    # Mark complete when Chinese summary exists, or when source summary/abstract are both unavailable.
    if has_meaningful_text(raw.get("summary_zh"), min_len=16):
        return True
    if not has_meaningful_text(raw.get("summary_en")) and not has_meaningful_text(raw.get("abstract")):
        return True
    return False


def parse_paper(session: requests.Session, date: str, hf_url: str) -> PaperRecord:
    html = fetch_html(session, hf_url)
    soup = BeautifulSoup(html, "lxml")

    paper_id = urlparse(hf_url).path.rstrip("/").split("/")[-1]
    paper_payload = extract_paper_payload(soup)
    title = extract_title(soup)
    authors = extract_authors(soup)
    abstract = extract_abstract(soup)
    summary_en = extract_summary_en(soup, paper_payload=paper_payload)
    arxiv_url = find_arxiv_url(soup, paper_id)
    arxiv_pdf_url = build_arxiv_pdf_url(arxiv_url)
    github_url = extract_github_url(soup, paper_payload)
    upvotes = extract_upvotes(soup, paper_payload)

    fetched_at = datetime.now(timezone.utc).isoformat()
    return PaperRecord(
        date=date,
        paper_id=paper_id,
        title=title,
        authors=authors,
        abstract=abstract,
        summary_en=summary_en,
        summary_zh="",
        hf_url=hf_url,
        arxiv_url=arxiv_url,
        arxiv_pdf_url=arxiv_pdf_url,
        github_url=github_url,
        upvotes=upvotes,
        fetched_at=fetched_at,
    )


def validate_date(date_text: str) -> str:
    try:
        datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date: {date_text}") from exc
    return date_text


def is_weekend_date(date_text: str) -> bool:
    dt = datetime.strptime(date_text, "%Y-%m-%d")
    return dt.weekday() >= 5


def write_paper_json(output_dir: Path, record: PaperRecord) -> Path:
    target = output_path_for_paper(output_dir, record.date, record.paper_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        json.dump(record.to_dict(), fh, ensure_ascii=False, indent=2)
    return target


def run(
    date: str,
    output_dir: Path,
    min_sleep: float,
    max_sleep: float,
    skip_existing_complete: bool,
    allow_weekend: bool,
) -> None:
    if is_weekend_date(date) and not allow_weekend:
        logging.info("Skip fetch for %s: weekend (Sat/Sun)", date)
        return

    date_url = HF_DATE_URL_TMPL.format(date=date)
    session = make_session()

    logging.info("Fetching daily list from %s", date_url)
    day_html = fetch_html(session, date_url)
    paper_urls = parse_paper_urls_from_date_page(day_html)

    if not paper_urls:
        logging.warning("No paper URLs found for %s", date)
        return

    logging.info("Found %d papers for %s", len(paper_urls), date)
    success_count = 0
    skipped_existing = 0

    for idx, hf_url in enumerate(paper_urls, start=1):
        logging.info("[%d/%d] Processing %s", idx, len(paper_urls), hf_url)
        paper_id = urlparse(hf_url).path.rstrip("/").split("/")[-1]
        output_path = output_path_for_paper(output_dir, date, paper_id)
        if skip_existing_complete and is_complete_existing_json(
            output_path,
            date=date,
            paper_id=paper_id,
            hf_url=hf_url,
        ):
            logging.info("Skip existing complete JSON: %s", output_path)
            skipped_existing += 1
            continue

        try:
            paper = parse_paper(session, date=date, hf_url=hf_url)
            path = write_paper_json(output_dir, paper)
            logging.info("Saved %s", path)
            success_count += 1
        except Exception as exc:  # noqa: BLE001
            logging.exception("Failed to parse %s: %s", hf_url, exc)

        if idx < len(paper_urls):
            sleep_s = random.uniform(min_sleep, max_sleep)
            time.sleep(sleep_s)

    logging.info(
        "Done. success=%d skipped_existing=%d total=%d",
        success_count,
        skipped_existing,
        len(paper_urls),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Hugging Face papers for a date")
    parser.add_argument("--date", type=validate_date, required=True, help="Date in YYYY-MM-DD")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/papers"),
        help="Output directory for per-paper JSON",
    )
    parser.add_argument("--min-sleep", type=float, default=0.5, help="Minimum sleep between papers")
    parser.add_argument("--max-sleep", type=float, default=1.5, help="Maximum sleep between papers")
    parser.add_argument(
        "--skip-existing-complete",
        action="store_true",
        help="Skip fetching paper when existing JSON is already complete",
    )
    parser.add_argument(
        "--allow-weekend",
        action="store_true",
        help="Allow fetch on weekend dates (default is skip Saturday/Sunday)",
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    if args.min_sleep > args.max_sleep:
        raise SystemExit("--min-sleep cannot be greater than --max-sleep")

    run(
        date=args.date,
        output_dir=args.output_dir,
        min_sleep=args.min_sleep,
        max_sleep=args.max_sleep,
        skip_existing_complete=args.skip_existing_complete,
        allow_weekend=args.allow_weekend,
    )


if __name__ == "__main__":
    main()
