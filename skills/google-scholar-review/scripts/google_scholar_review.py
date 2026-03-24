#!/usr/bin/env python3
"""Google Scholar literature-review helper using SerpAPI."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

import requests

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
    "using",
    "based",
    "toward",
    "towards",
    "study",
    "studies",
    "evidence",
    "analysis",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Google Scholar review workflow helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Search Google Scholar via SerpAPI")
    add_common_search_args(search_parser)

    outline_parser = subparsers.add_parser("outline", help="Generate review outline from JSON")
    outline_parser.add_argument("--input-json", type=Path, required=True)
    outline_parser.add_argument("--output-md", type=Path, required=True)
    outline_parser.add_argument("--topic", required=True)

    pipeline_parser = subparsers.add_parser("pipeline", help="Run search + outline")
    add_common_search_args(pipeline_parser)
    pipeline_parser.add_argument("--topic", help="Optional topic for outline header")

    return parser.parse_args()


def add_common_search_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--query", required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--year-start", type=int)
    parser.add_argument("--year-end", type=int)
    parser.add_argument("--max-results", type=int, default=20)


def run_scholar_search(
    query: str,
    year_start: int | None,
    year_end: int | None,
    max_results: int,
) -> list[dict[str, Any]]:
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing SERPAPI_API_KEY environment variable.")

    records: list[dict[str, Any]] = []
    fetched = 0
    page_size = 20

    while fetched < max_results:
        num = min(page_size, max_results - fetched)
        params = {
            "engine": "google_scholar",
            "q": query,
            "api_key": api_key,
            "num": num,
            "start": fetched,
            "hl": "en",
        }
        if year_start is not None:
            params["as_ylo"] = year_start
        if year_end is not None:
            params["as_yhi"] = year_end

        response = requests.get(SERPAPI_ENDPOINT, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        organic = payload.get("organic_results", [])
        if not organic:
            break

        for item in organic:
            result_id = item.get("result_id", "")
            pub_info = item.get("publication_info", {})
            authors = pub_info.get("authors", []) or []
            cited = item.get("inline_links", {}).get("cited_by", {}).get("total", 0)
            year = extract_year(item)

            records.append(
                {
                    "result_id": result_id,
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "authors": "; ".join(a.get("name", "") for a in authors if a.get("name")),
                    "publication_summary": pub_info.get("summary", ""),
                    "year": year,
                    "citations": int(cited) if isinstance(cited, int) else 0,
                }
            )

        fetched += len(organic)
        if len(organic) < num:
            break

    return records


def extract_year(item: dict[str, Any]) -> int | None:
    summary = item.get("publication_info", {}).get("summary", "") or ""
    match = re.search(r"(19|20)\d{2}", summary)
    if match:
        return int(match.group(0))
    return None


def ensure_workspace_paths(workspace: Path) -> dict[str, Path]:
    paths = {
        "json": workspace / "01_search" / "google_scholar_results.json",
        "csv": workspace / "01_search" / "google_scholar_results.csv",
        "evidence": workspace / "03_screening" / "scholar_evidence_table.csv",
        "outline": workspace / "07_plan" / "google_scholar_outline.md",
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    return paths


def write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "result_id",
        "title",
        "link",
        "authors",
        "year",
        "citations",
        "publication_summary",
        "snippet",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_evidence_table(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "paper_key",
        "title",
        "year",
        "authors",
        "citations",
        "main_finding",
        "method",
        "theory",
        "keep_for_review",
        "source_link",
    ]

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for idx, row in enumerate(rows, start=1):
            writer.writerow(
                {
                    "paper_key": f"scholar-{idx:04d}",
                    "title": row.get("title", ""),
                    "year": row.get("year", ""),
                    "authors": row.get("authors", ""),
                    "citations": row.get("citations", ""),
                    "main_finding": row.get("snippet", ""),
                    "method": "",
                    "theory": "",
                    "keep_for_review": "pending",
                    "source_link": row.get("link", ""),
                }
            )


def build_outline(topic: str, rows: list[dict[str, Any]]) -> str:
    sorted_rows = sorted(rows, key=lambda x: x.get("citations", 0), reverse=True)
    top_rows = sorted_rows[:10]

    token_counter: Counter[str] = Counter()
    for row in top_rows:
        text = f"{row.get('title', '')} {row.get('snippet', '')}".lower()
        tokens = re.findall(r"[a-z]{4,}", text)
        token_counter.update(t for t in tokens if t not in STOPWORDS)

    themes = [token for token, _ in token_counter.most_common(6)]
    while len(themes) < 3:
        themes.append(f"theme-{len(themes) + 1}")

    lines: list[str] = []
    lines.append(f"# Literature Review Outline: {topic}")
    lines.append("")
    lines.append("## 1. Introduction")
    lines.append("- Motivate the research problem and managerial relevance.")
    lines.append("- Define scope, boundaries, and core constructs.")
    lines.append("")
    lines.append("## 2. Core Themes from Scholar Scan")
    for index, theme in enumerate(themes[:3], start=1):
        lines.append(f"### 2.{index} Theme: {theme}")
        lines.append("- Key findings:")
        lines.append("- Dominant methods:")
        lines.append("- Contradictions and boundary conditions:")
        lines.append("")

    lines.append("## 3. Integrative Framework")
    lines.append("- Explain how themes connect causally or temporally.")
    lines.append("- State the proposed synthesis model.")
    lines.append("")
    lines.append("## 4. Future Research Agenda")
    lines.append("- Theoretical opportunities")
    lines.append("- Methodological opportunities")
    lines.append("- Context and boundary opportunities")
    lines.append("")
    lines.append("## Appendix A. Priority Papers (Top by citation count)")
    for row in top_rows[:8]:
        lines.append(
            f"- {row.get('title', '')} ({row.get('year', 'n/a')}) | citations={row.get('citations', 0)}"
        )

    return "\n".join(lines) + "\n"


def run_search(args: argparse.Namespace) -> dict[str, Path]:
    paths = ensure_workspace_paths(args.workspace)
    rows = run_scholar_search(args.query, args.year_start, args.year_end, args.max_results)
    write_json(paths["json"], rows)
    write_csv(paths["csv"], rows)
    write_evidence_table(paths["evidence"], rows)
    print(f"Saved {len(rows)} records to {paths['json']}")
    return paths


def run_outline(input_json: Path, output_md: Path, topic: str) -> None:
    rows = json.loads(input_json.read_text(encoding="utf-8"))
    outline = build_outline(topic=topic, rows=rows)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(outline, encoding="utf-8")
    print(f"Outline written to {output_md}")


def main() -> None:
    args = parse_args()
    if args.command == "search":
        run_search(args)
        return
    if args.command == "outline":
        run_outline(args.input_json, args.output_md, args.topic)
        return
    if args.command == "pipeline":
        paths = run_search(args)
        topic = args.topic or args.query
        run_outline(paths["json"], paths["outline"], topic)
        return

    raise RuntimeError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
