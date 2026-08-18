#!/usr/bin/env python3
"""Sanity checks for the static site in site/.

Run locally with: python3 tools/check_site.py

Checks the content only. The custom domain is not this script's business: it
is bound by the repo's Pages setting, and pages.yml asserts that setting
against the live Pages API after each deploy.
"""

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

SITE = Path(__file__).resolve().parent.parent / "site"
REQUIRED = ["index.html", "404.html"]

# Tags that never have a closing partner, so tag balancing must skip them.
VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}

# HTML permits omitting these end tags. A second <li> closes the first, and the
# parent's </ul> closes the last. Without this the balance check reports valid
# markup as broken.
OPTIONAL_END = {
    "li": {"li"},
    "p": {"p"},
    "dt": {"dt", "dd"},
    "dd": {"dt", "dd"},
    "td": {"td", "th", "tr"},
    "th": {"td", "th", "tr"},
    "tr": {"tr"},
    "option": {"option"},
    "thead": {"tbody", "tfoot"},
    "tbody": {"tbody", "tfoot"},
}

# Smallest plausible bundle. site/index.html is a ~2.75 MB generated blob; an
# empty or stub file would otherwise pass every other check vacuously.
MIN_INDEX_BYTES = 100_000
INDEX_MARKERS = ("__bundler/manifest", "__bundler/template")

errors = []


class Checker(HTMLParser):
    """Collects local link targets and verifies tags nest correctly."""

    def __init__(self, path):
        super().__init__()
        self.path = path
        self.stack = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        # An open optional-end tag is closed by a sibling that implies it.
        while self.stack and tag in OPTIONAL_END.get(self.stack[-1][0], ()):
            self.stack.pop()
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))
        for name, value in attrs:
            if name in ("href", "src") and value:
                self.links.append((value, self.getpos()[0]))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        # A parent's end tag closes any optional-end children still open.
        while self.stack and self.stack[-1][0] != tag and self.stack[-1][0] in OPTIONAL_END:
            self.stack.pop()
        if not self.stack:
            errors.append(f"{self.path.name}:{self.getpos()[0]}: stray </{tag}>")
        elif self.stack[-1][0] != tag:
            open_tag, open_line = self.stack[-1]
            errors.append(
                f"{self.path.name}:{self.getpos()[0]}: </{tag}> closes "
                f"<{open_tag}> opened on line {open_line}"
            )
            self.stack.pop()
        else:
            self.stack.pop()


def check_links(page, links):
    for target, line in links:
        # Skip anything that leaves the site or is not a filesystem path.
        if urlparse(target).scheme or target.startswith(("//", "#", "mailto:", "data:")):
            continue
        clean = target.split("#")[0].split("?")[0]
        if not clean:
            continue
        resolved = SITE / clean.lstrip("/") if clean.startswith("/") else page.parent / clean
        # A directory link is served by its index.html.
        if resolved.is_dir():
            resolved = resolved / "index.html"
        if not resolved.exists():
            errors.append(f"{page.name}:{line}: broken local link {target!r}")


def main(argv):
    ci = False
    for arg in argv:
        if arg == "--ci":
            ci = True
        else:
            print(f"usage: check_site.py [--ci]   (unknown argument {arg!r})", file=sys.stderr)
            return 2

    if not SITE.is_dir():
        print(f"error: {SITE} does not exist", file=sys.stderr)
        return 1

    for name in REQUIRED:
        if not (SITE / name).exists():
            errors.append(f"missing required file site/{name}")

    # index.html is a generated bundle, so "present" is not enough: whole-file
    # loss leaves a file that parses cleanly and links to nothing.
    index = SITE / "index.html"
    if index.exists():
        blob = index.read_text(encoding="utf-8")
        if len(blob) < MIN_INDEX_BYTES:
            errors.append(
                f"site/index.html is {len(blob)} bytes; the bundle should be "
                f"at least {MIN_INDEX_BYTES}"
            )
        for marker in INDEX_MARKERS:
            if marker not in blob:
                errors.append(f"site/index.html is missing {marker!r}")

    for page in sorted(SITE.rglob("*.html")):
        parser = Checker(page)
        parser.feed(page.read_text(encoding="utf-8"))
        parser.close()
        for tag, line in parser.stack:
            errors.append(f"{page.name}: <{tag}> opened on line {line} is never closed")
        check_links(page, parser.links)

    if errors:
        for e in errors:
            print(f"::error::{e}" if ci else e)
        return 1

    pages = sorted(p.name for p in SITE.rglob("*.html"))
    print(f"ok: {len(pages)} page(s) [{', '.join(pages)}]")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
