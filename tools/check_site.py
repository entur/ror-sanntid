#!/usr/bin/env python3
"""Sanity checks for the static site in site/.

Run locally with: python3 tools/check_site.py

Checks the content only. The custom domain is not this script's business: it
is bound by the repo's Pages setting, and pages.yml asserts that setting
against the live Pages API after each deploy.
"""

import re
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

# Every page must have these, whatever else it contains. Without such a floor
# an empty file passes every other check vacuously: no tags to unbalance and no
# links to break. Deliberately structural rather than size- or content-based,
# so a page can be rewritten, shrunk or replaced without CI objecting.
REQUIRED_TAGS = ("html", "body", "title")

# Most external links are listed twice on every page: "Enturs rolle" spells each
# one out in a prose panel, "Dokumentasjon og tjenester" repeats it in a bare
# index. Both pages carry both sections, so one URL change is four identical
# edits and nothing else notices when only some of them happen.
LINK_SECTIONS = ("enturs-rolle", "dokumentasjon")

# What the prose section may carry without the index repeating it. Everything
# else present in one section and not the other is drift between the two.
PROSE_ONLY = {
    "https://data.entur.no/public/insights",
    "https://www.entur.no",
}

errors = []


class Checker(HTMLParser):
    """Collects local link targets and verifies tags nest correctly."""

    def __init__(self, path):
        super().__init__()
        self.path = path
        self.stack = []
        self.links = []
        self.seen = set()
        self.ids = []
        self.title = ""
        self._in_title = False
        # section id -> {external url: first line seen}
        self.section_links = {}
        # (section id, stack depth of its element), innermost last
        self._sections = []

    def handle_starttag(self, tag, attrs):
        self.seen.add(tag)
        for name, value in attrs:
            if name == "id" and value:
                self.ids.append((value, self.getpos()[0]))
        if tag == "title":
            self._in_title = True
        # An open optional-end tag is closed by a sibling that implies it.
        while self.stack and tag in OPTIONAL_END.get(self.stack[-1][0], ()):
            self.stack.pop()
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))
            for name, value in attrs:
                if name == "id" and value in LINK_SECTIONS:
                    self._sections.append((value, len(self.stack)))
                    self.section_links.setdefault(value, {})
        for name, value in attrs:
            if name in ("href", "src") and value:
                self.links.append((value, self.getpos()[0]))
                if self._sections and urlparse(value).scheme in ("http", "https"):
                    self.section_links[self._sections[-1][0]].setdefault(
                        value, self.getpos()[0]
                    )

    def handle_data(self, data):
        if self._in_title:
            self.title += data

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
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
        while self._sections and len(self.stack) < self._sections[-1][1]:
            self._sections.pop()


def check_links(page, links, ids=frozenset()):
    for target, line in links:
        # Skip anything that leaves the site or is not a filesystem path.
        if urlparse(target).scheme or target.startswith(("//", "mailto:", "data:")):
            continue
        # Same-page fragment: the site navigates almost entirely this way, so a
        # typo here is a dead link that nothing else would catch.
        if target.startswith("#"):
            frag = target[1:]
            if frag and frag not in ids:
                errors.append(f"{page.name}:{line}: fragment {target!r} matches no id")
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


def check_link_sections(page, section_links):
    """Compare the external links of the prose panels against the link index.

    Catches the URL updated in one of the two sections and left stale in the
    other, which no other check here would see: both spellings resolve, and
    neither is a local path.
    """
    prose_id, index_id = LINK_SECTIONS
    missing = [s for s in LINK_SECTIONS if s not in section_links]
    if len(missing) == len(LINK_SECTIONS):
        return
    if missing:
        errors.append(
            f"{page.name}: no #{missing[0]} section, so its link list cannot be "
            f"compared against #{[s for s in LINK_SECTIONS if s not in missing][0]}"
        )
        return
    prose, index = section_links[prose_id], section_links[index_id]
    for url in sorted(index.keys() - prose.keys()):
        errors.append(
            f"{page.name}:{index[url]}: {url} is listed in #{index_id} "
            f"but not in #{prose_id}"
        )
    for url in sorted(prose.keys() - index.keys() - PROSE_ONLY):
        errors.append(
            f"{page.name}:{prose[url]}: {url} is listed in #{prose_id} "
            f"but not in #{index_id}"
        )
    # Keeps the allowlist from outliving its reason.
    for url in sorted(PROSE_ONLY & index.keys()):
        errors.append(
            f"{page.name}:{index[url]}: {url} now appears in #{index_id} too; "
            f"drop it from PROSE_ONLY in {Path(__file__).name}"
        )


def check_css(path):
    """Resolve url() targets in a stylesheet, relative to the stylesheet."""
    for m in re.finditer(r"url\(\s*['\"]?([^)'\"]+)['\"]?\s*\)", path.read_text(encoding="utf-8")):
        target = m.group(1).strip()
        if urlparse(target).scheme or target.startswith(("//", "data:", "#")):
            continue
        line = path.read_text(encoding="utf-8")[: m.start()].count("\n") + 1
        resolved = SITE / target.lstrip("/") if target.startswith("/") else path.parent / target
        if not resolved.exists():
            errors.append(f"{path.name}:{line}: broken url() {target!r}")


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

    for page in sorted(SITE.rglob("*.html")):
        parser = Checker(page)
        parser.feed(page.read_text(encoding="utf-8"))
        parser.close()
        for tag, line in parser.stack:
            errors.append(f"{page.name}: <{tag}> opened on line {line} is never closed")
        for tag in REQUIRED_TAGS:
            if tag not in parser.seen:
                errors.append(f"{page.name}: no <{tag}> element")
        if "title" in parser.seen and not parser.title.strip():
            errors.append(f"{page.name}: <title> is empty")
        seen_ids = {}
        for value, line in parser.ids:
            if value in seen_ids:
                errors.append(
                    f"{page.name}:{line}: duplicate id {value!r} (first at line {seen_ids[value]})"
                )
            else:
                seen_ids[value] = line
        check_links(page, parser.links, frozenset(seen_ids))
        check_link_sections(page, parser.section_links)

    # Fonts and background images referenced only from CSS are invisible to the
    # HTML link check above.
    for sheet in sorted(SITE.rglob("*.css")):
        check_css(sheet)

    if errors:
        for e in errors:
            print(f"::error::{e}" if ci else e)
        return 1

    pages = sorted(p.name for p in SITE.rglob("*.html"))
    print(f"ok: {len(pages)} page(s) [{', '.join(pages)}]")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
