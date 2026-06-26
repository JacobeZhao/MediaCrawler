import argparse
import csv
import json
from pathlib import Path
from urllib import request


def _load_keywords(path: Path) -> list[str]:
    if path.suffix.lower() == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            values = raw
        else:
            values = raw.get("keywords", [])
        return [str(v).strip() for v in values if str(v).strip()]

    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        if rows:
            preferred = ["月度", "月度关键词", "keyword", "关键词", "搜索词"]
            field = next((name for name in preferred if name in rows[0]), None)
            if field:
                return [row[field].strip() for row in rows if row.get(field, "").strip()]
        return []

    return [line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def _post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Create MediaCrawler search tasks from keyword file.")
    parser.add_argument("keywords_file", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8088")
    parser.add_argument("--max-notes", type=int, default=200)
    parser.add_argument("--max-comments", type=int, default=10000)
    parser.add_argument("--sort-type", default="time_descending")
    parser.add_argument("--days-limit", type=int, default=31)
    args = parser.parse_args()

    keywords = list(dict.fromkeys(_load_keywords(args.keywords_file)))
    if not keywords:
        raise SystemExit(f"No keywords loaded from {args.keywords_file}")

    payload = {
        "keywords": keywords,
        "max_notes": args.max_notes,
        "max_comments": args.max_comments,
        "sort_type": args.sort_type,
        "days_limit": args.days_limit,
    }
    result = _post_json(f"{args.base_url.rstrip('/')}/api/tasks/batch_search", payload)
    print(json.dumps({"keywords": len(keywords), "result": result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
