#!/usr/bin/env python3
"""Split the source markdown file into pages of at most `char_limit` characters,
write an index of links to them, and build a bare-bones HTML site for GitHub Pages.

Settings live in paginate.json at the repo root. Pages are cut at the cleanest
boundary that fits: a `---` divider between turns, then a blank line, then a
line break, then a space, and only as a last resort mid-word. Pages are an
exact slice of the source, so joining them in order reproduces it.

The HTML site is deliberately minimal (no JavaScript, one line of CSS) so an
agent reading it gets the story text without GitHub's page overhead. Index
links point at the GitHub Pages HTML files; the base URL comes from the
PAGES_BASE_URL environment variable set by the workflow.
"""
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
BREAKS = ["\n\n---\n\n", "\n\n", "\n", " "]
STRUCTURE_LINE = re.compile(r"^\s*(#{1,6}\s.*|[-*_]{3,})\s*$")  # headings, dividers
URL = re.compile(r"https?://\S+")

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>body{{max-width:46em;margin:2em auto;padding:0 1em;font-family:sans-serif;line-height:1.5}}</style>
</head>
<body>
{body}
</body>
</html>
"""


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


def preview(page, length):
    """The first `length` characters of a page's text on one line. Headings,
    dividers, URLs and * emphasis are dropped so the preview is plain story
    text and the index contains no links other than the pages."""
    lines = [l for l in page.splitlines() if l.strip() and not STRUCTURE_LINE.match(l)]
    text = URL.sub("", " ".join(lines)).replace("*", "")
    text = " ".join(text.split())
    return text if len(text) <= length else text[:length].rstrip() + "…"


def pages_base_url():
    """GitHub Pages URL of the site when running in Actions, or "" locally
    (links are then relative, which is only meant for testing)."""
    base = os.environ.get("PAGES_BASE_URL", "").rstrip("/")
    if not base:
        print("PAGES_BASE_URL not set; writing relative links (local test only)")
        return ""
    return base + "/"


def reset_dir(path):
    if path == ROOT or ROOT not in path.parents:
        sys.exit(f"{path} must be a subfolder of the repo")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def main():
    config = json.loads((ROOT / "paginate.json").read_text(encoding="utf-8"))
    source = ROOT / config["source"]
    limit = int(config["char_limit"])
    preview_chars = int(config.get("preview_chars", 0))
    out_dir = (ROOT / config.get("output_dir", "pages")).resolve()
    site_dir = (ROOT / config.get("site_dir", "_site")).resolve()
    index = ROOT / config.get("index", "index.md")

    if limit < 1:
        sys.exit("char_limit must be at least 1")

    import markdown  # needed only here so a missing package fails before any files are touched

    text = source.read_text(encoding="utf-8")
    pages = paginate(text, limit)

    # Regenerate from scratch so a higher limit doesn't leave stale pages behind.
    reset_dir(out_dir)
    reset_dir(site_dir)
    site_pages = site_dir / out_dir.relative_to(ROOT)
    site_pages.mkdir(parents=True)

    base = pages_base_url()
    width = max(3, len(str(len(pages))))
    md_lines, html_items = [], []
    for n, page in enumerate(pages, 1):
        stem = f"{source.stem}-{n:0{width}d}"
        (out_dir / f"{stem}{source.suffix}").write_text(page, encoding="utf-8", newline="\n")
        (site_pages / f"{stem}.html").write_text(
            HTML_PAGE.format(title=html.escape(stem), body=markdown.markdown(page)),
            encoding="utf-8", newline="\n")

        url = base + quote(f"{site_pages.relative_to(site_dir).as_posix()}/{stem}.html")
        blurb = preview(page, preview_chars) if preview_chars > 0 else ""
        md_lines.append(f"- {url} — {blurb}" if blurb else f"- {url}")
        link = f'<a href="{html.escape(url)}">{html.escape(url)}</a>'
        html_items.append(f"<li>{link} — {html.escape(blurb)}</li>" if blurb else f"<li>{link}</li>")

    index.write_text("\n".join(md_lines) + "\n", encoding="utf-8", newline="\n")
    (site_dir / "index.html").write_text(
        HTML_PAGE.format(title=html.escape(source.stem),
                         body="<ul>\n" + "\n".join(html_items) + "\n</ul>"),
        encoding="utf-8", newline="\n")
    print(f"{len(text)} chars -> {len(pages)} pages (limit {limit}); site in {site_dir.name}/")


if __name__ == "__main__":
    main()
