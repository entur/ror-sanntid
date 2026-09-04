#!/usr/bin/env python3
"""Split the self-unpacking bundle in site/index.html into real files.

The bundle is a Claude-artifact style package: a manifest of gzipped+base64
assets keyed by uuid, plus a JSON-escaped HTML template that references those
uuids. The runtime loader mints blob: URLs and substitutes them at load time,
which means every byte ships on every page load and nothing can be cached
independently. This writes the assets out as files and rewrites the template to
point at them.

The bundle carries both languages in one document as [data-lang-pane] blocks
that a script shows and hides. That makes English unreachable without
JavaScript and gives the two versions one URL, so this splits them into
index.html and en/index.html around the shared chrome, drops the `-en` id
suffixes the single document needed to stay unique, and turns the language
buttons into ordinary links.

Output still needs the site conventions applied by hand afterwards: the head
metadata, the skip link, img width/height, the accordions shipping expanded for
no-JS readers, and `npx prettier --write site/`.
"""
import base64, gzip, json, pathlib, re, sys

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
SRC = ROOT / "site" / "index.html"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "site"

# Image uuid -> path under assets/. Named from each image's alt text and the
# heading above it. Fonts are not listed here: their names are derived from the
# @font-face rules that reference them, so no uuid needs transcribing by hand.
IMAGES = {
    "9bffada7-578d-482e-b67b-af6ebc2a29c9": "img/icon-doc.svg",
    "8ed523ad-f28a-4365-b563-378ee040e23f": "img/entur-logo.png",
    "0b92e341-2885-403c-9988-807408ae79af": "img/reisedetaljer-siri.png",
    "1eddecaa-4611-4205-9e19-2fbc91083ce0": "img/sanntid-i-bruk.png",
    "9ca2fa1c-7dcc-4fda-91f4-79126c454054": "img/hero-illustrasjon.svg",
    "ccbb25d1-6ecf-48ff-8e72-92c5091990a6": "img/diagram-hvordan-fungerer-det.svg",
    "61a5a7d0-3a64-468a-9a19-226c21561394": "img/diagram-data-inn.svg",
    "f46c4944-61aa-41f8-83a2-a4f35e76b74e": "img/diagram-hva-tilbyr-entur.svg",
    "1215b1f3-38c6-4ab0-9a76-9ceba7edc7c7": "img/diagram-komme-i-gang.svg",
    "2367ddf4-291c-4a9c-8eee-36b87ab0e28e": "img/hero-illustrasjon-en.svg",
    "5bdc953e-a07e-4fca-9722-00f380c10e0d": "img/diagram-hvordan-fungerer-det-en.svg",
    "47289263-035c-4d77-ba6b-9c339dfd9bb6": "img/diagram-data-inn-en.svg",
    "acc6c296-4533-4b3a-8416-7741b921ab24": "img/diagram-hva-tilbyr-entur-en.svg",
    "6a214506-42fe-4e14-af0c-06a082673edf": "img/diagram-komme-i-gang-en.svg",
}


def font_names(template):
    """uuid -> fonts/<family>-<weight>[-italic].woff2, read from @font-face."""
    out = {}
    for block in re.findall(r"@font-face\s*\{(.*?)\}", template, re.S):
        uid = re.search(r'url\("([0-9a-f-]{36})"\)', block)
        fam = re.search(r'font-family:\s*"([^"]+)"', block)
        weight = re.search(r"font-weight:\s*(\d+)", block)
        style = re.search(r"font-style:\s*(\w+)", block)
        if not (uid and fam and weight):
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", fam.group(1).lower()).strip("-")
        italic = "-italic" if style and style.group(1) == "italic" else ""
        out[uid.group(1)] = f"fonts/{slug}-{weight.group(1)}{italic}.woff2"
    return out


def grab(src, kind):
    m = re.search(r'<script type="__bundler/%s">(.*?)</script>' % kind, src, re.S)
    return m.group(1) if m else None


def cut_element(html, opening):
    """Return (before, inner, after) for the element starting at `opening`.

    Only <div> nesting is counted, which is all the panes contain at their own
    level. A regex cannot do this: the panes wrap most of the document.
    """
    start = html.index(opening)
    depth, i = 0, start
    for m in re.finditer(r"<div\b|</div>", html[start:]):
        depth += 1 if m.group(0) == "<div" else -1
        if depth == 0:
            i = start + m.end()
            break
    else:
        sys.exit(f"refusing: {opening} is never closed")
    return html[:start], html[start + len(opening) : i - len("</div>")], html[i:]


# The language switch is a pair of buttons driven by the pane script. As
# separate pages it becomes a pair of links, which works without JavaScript and
# gives each language a URL that can be shared and indexed.
LANGSWITCH = re.compile(r'<div class="langswitch".*?</div>', re.S)
LANGLINKS = """<nav class="langswitch" aria-label="Språk · Language">
      <a href="{no}" hreflang="no" lang="no"{no_current}>Norsk</a>
      <a href="{en}" hreflang="en" lang="en"{en_current}>English</a>
    </nav>"""


def main():
    src = SRC.read_text(encoding="utf-8")
    raw_manifest, raw_template = grab(src, "manifest"), grab(src, "template")
    if not raw_manifest or not raw_template:
        sys.exit(
            f"{SRC} is not a bundle: no __bundler/manifest or __bundler/template "
            "script tag. This is one-off migration tooling — the site has already "
            "been unbundled. To re-import a fresh Claude artifact export, overwrite "
            "site/index.html with the exported bundle first, then run this again."
        )
    manifest = json.loads(raw_manifest)
    template = json.loads(raw_template)
    page_order = json.loads(grab(src, "page_order") or "[]")
    if page_order:
        sys.exit(f"refusing: bundle has {len(page_order)} nested page(s), not handled")

    names = dict(IMAGES)
    names.update(font_names(template))
    missing = set(manifest) - set(names)
    if missing:
        sys.exit(f"refusing: {len(missing)} asset(s) have no filename: {sorted(missing)}")
    unused = set(names) - set(manifest)
    if unused:
        sys.exit(f"refusing: {len(unused)} name(s) match no asset: {sorted(unused)}")

    # 1. Assets to disk, decompressed.
    for uid, entry in manifest.items():
        blob = base64.b64decode(entry["data"])
        if entry.get("compressed"):
            blob = gzip.decompress(blob)
        dest = OUT / "assets" / names[uid]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)

    # 2. Pull the inline CSS and JS out of the template.
    styles = re.findall(r"<style[^>]*>(.*?)</style>", template, re.S)
    scripts = re.findall(r"<script(?![^>]*src=)[^>]*>(.*?)</script>", template, re.S)
    css = "\n\n".join(s.strip() for s in styles)
    js = "\n\n".join(s.strip() for s in scripts)

    # 3. Rewrite uuid references. Paths differ by referrer: the CSS lives at
    #    assets/styles.css so it addresses siblings, while index.html is a
    #    level above and must go through assets/.
    for uid, rel in names.items():
        css = css.replace(f'url("{uid}")', f'url("{rel}")')
        template = template.replace(f'src="{uid}"', f'src="assets/{rel}"')
    (OUT / "assets" / "styles.css").write_text(css + "\n", encoding="utf-8")
    if js:
        (OUT / "assets" / "app.js").write_text(js + "\n", encoding="utf-8")

    # 4. Swap the inline blocks for links. First <style> becomes the
    #    stylesheet link, any others are dropped (their text is in the file).
    seen = {"style": 0, "script": 0}

    def sub_style(_m):
        seen["style"] += 1
        if seen["style"] == 1:
            return '<link rel="stylesheet" href="assets/styles.css">'
        return ""

    def sub_script(_m):
        seen["script"] += 1
        if seen["script"] == 1 and js:
            return '<script src="assets/app.js" defer></script>'
        return ""

    template = re.sub(r"<style[^>]*>.*?</style>", sub_style, template, flags=re.S)
    template = re.sub(r"<script(?![^>]*src=)[^>]*>.*?</script>", sub_script, template, flags=re.S)

    # 5. Preload the two faces used for body text, so the swap is less visible.
    preloads = "\n".join(
        f'<link rel="preload" href="assets/fonts/nationale-{w}.woff2" as="font" '
        f'type="font/woff2" crossorigin>' for w in ("400", "600")
    )
    template = template.replace(
        '<link rel="stylesheet" href="assets/styles.css">',
        preloads + '\n<link rel="stylesheet" href="assets/styles.css">', 1)

    # 6. Drop the artifact preview's thumbnail placeholder.
    template = re.sub(
        r'\s*<template id="__bundler_thumbnail".*?</template>', "", template, flags=re.S)

    # Only meaningful now: until the inline <style> blocks were replaced above,
    # the font uuids still appeared in the template by construction.
    for uid in names:
        if uid in template:
            sys.exit(f"refusing: uuid {uid} still in html after rewrite")
        if uid in css:
            sys.exit(f"refusing: uuid {uid} still in css after rewrite")
    if "__bundler" in template:
        sys.exit("refusing: bundler scaffolding still present in html")

    # 7. Split the two language panes out of the shared chrome into one page
    #    each. Whatever surrounds the panes — head, header, scripts — is
    #    common, so each page is the chrome with its own pane spliced back in.
    head, no_pane, rest = cut_element(template, '<div data-lang-pane="no">')
    mid, en_pane, tail = cut_element(rest, '<div data-lang-pane="en" hidden="">')
    if 'data-lang-pane' in head + mid + tail:
        sys.exit("refusing: more than two language panes")

    pages = {}
    for lang, pane in (("no", no_pane), ("en", en_pane)):
        page = head + pane + mid + tail
        page = page.replace('<html lang="no">', f'<html lang="{lang}">', 1)
        page, swapped = LANGSWITCH.subn(LANGLINKS.format(
            no="../" if lang == "en" else "./",
            en="./" if lang == "en" else "en/",
            no_current="" if lang == "en" else ' aria-current="page"',
            en_current=' aria-current="page"' if lang == "en" else "",
        ), page, count=1)
        if not swapped:
            sys.exit("refusing: no .langswitch to turn into links")
        if lang == "en":
            # The `-en` suffixes only existed to keep ids unique while both
            # languages shared a document.
            page = re.sub(r'((?:id|aria-controls)="[^"]+?|href="#[^"]+?)-en"', r'\1"', page)
            # One directory deeper than the Norwegian page.
            page = page.replace('="assets/', '="../assets/')
        pages[lang] = page

    (OUT / "index.html").write_text(pages["no"], encoding="utf-8")
    (OUT / "en").mkdir(parents=True, exist_ok=True)
    (OUT / "en" / "index.html").write_text(pages["en"], encoding="utf-8")

    total = sum((OUT / "assets" / n).stat().st_size for n in names.values())
    print(f"assets   {len(names):>3} files  {total/1024:>9.1f} KiB")
    print(f"css              {len(css)/1024:>9.1f} KiB")
    print(f"js               {len(js)/1024:>9.1f} KiB")
    for lang, page in pages.items():
        print(f"html {lang:<3}         {len(page)/1024:>9.1f} KiB")


if __name__ == "__main__":
    main()
