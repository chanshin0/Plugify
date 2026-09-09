#!/usr/bin/env python3
"""작업 디렉터리의 JSON 파일에 링크를 보관한다."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser(description="팀 링크 모음")
sub = parser.add_subparsers(dest="action", required=True)
add = sub.add_parser("add", help="링크 추가")
add.add_argument("url")
add.add_argument("--title", required=True)
add.add_argument("--tag", action="append", default=[])
listing = sub.add_parser("list", help="링크 목록")
listing.add_argument("--tag")
search = sub.add_parser("search", help="제목 검색")
search.add_argument("query")
remove = sub.add_parser("remove", help="URL 삭제")
remove.add_argument("url")
args = parser.parse_args()
path = Path("links.json")
rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
if args.action == "add":
    rows = [row for row in rows if row["url"] != args.url]
    rows.append({"url": args.url, "title": args.title, "tags": args.tag})
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
elif args.action == "remove":
    kept = [row for row in rows if row["url"] != args.url]
    if len(kept) == len(rows):
        parser.exit(1, "해당 URL이 없습니다.\n")
    path.write_text(json.dumps(kept, ensure_ascii=False), encoding="utf-8")
else:
    for row in rows:
        if args.action == "list" and args.tag and args.tag not in row.get("tags", []):
            continue
        if args.action == "search" and args.query not in row["title"]:
            continue
        print(row["title"], row["url"])
