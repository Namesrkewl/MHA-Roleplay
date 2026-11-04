#!/usr/bin/env python3
"""Split the source markdown file into pages of at most `char_limit` characters,
then write an index file containing only links to those pages.

Settings live in paginate.json at the repo root. Pages are cut at the cleanest
boundary that fits: a `---` divider between turns, then a blank line, then a
line break, then a space, and only as a last resort mid-word. Pages are an
exact slice of the source, so joining them in order reproduces it.

Index links are full github.com page URLs (not raw.githubusercontent.com),
built from the repo and branch that GitHub Actions provides.
"""
import json
import os
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
BREAKS = ["\n\n---\n\n", "\n\n", "\n", " "]


def paginate(text, limit):
    pages = []
    start = 0
    while len(text) - start > limit:
        end = start + limit
        cut = end  # hard cut if no break point fits
        for sep in BREAKS:
            i = text.rfind(sep, start + 1, end)
            if i != -1:
                cut = i + len(sep)
                break
        pages.append(text[start:cut])
        start = cut
    if start < len(text):
        pages.append(text[start:])
    return pages


def link_base():
    """Prefix for index links: the github.com page URL when running in Actions,
    or relative paths when testing locally."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        print("GITHUB_REPOSITORY not set; writing relative links (local test only)")
        return ""
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    return f"{server}/{repo}/blob/{quote(branch)}/"


def main():
    config = json.loads((ROOT / "paginate.json").read_text(encoding="utf-8"))
    source = ROOT / config["source"]
    limit = int(config["char_limit"])
    out_dir = (ROOT / config.get("output_dir", "pages")).resolve()
    index = ROOT / config.get("index", "index.md")

    if limit < 1:
        sys.exit("char_limit must be at least 1")
    if out_dir == ROOT or ROOT not in out_dir.parents:
        sys.exit("output_dir must be a subfolder of the repo")

    text = source.read_text(encoding="utf-8")
    pages = paginate(text, limit)

    # Regenerate from scratch so a higher limit doesn't leave stale pages behind.
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    base = link_base()
    width = max(3, len(str(len(pages))))
    links = []
    for n, page in enumerate(pages, 1):
        name = f"{source.stem}-{n:0{width}d}{source.suffix}"
        (out_dir / name).write_text(page, encoding="utf-8", newline="\n")
        rel = out_dir.relative_to(ROOT).as_posix() + "/" + name
        links.append(f"- {base}{quote(rel)}")

    index.write_text("\n".join(links) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(text)} chars -> {len(pages)} pages (limit {limit})")


if __name__ == "__main__":
    main()
