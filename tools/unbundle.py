#!/usr/bin/env python3
"""Split the self-unpacking bundle in site/index.html into real files.

The bundle is a Claude-artifact style package: a manifest of gzipped+base64
assets keyed by uuid, plus a JSON-escaped HTML template that references those
uuids. The runtime loader mints blob: URLs and substitutes them at load time,
which means every byte ships on every page load and nothing can be cached
independently. This writes the assets out as files and rewrites the template to
point at them.
"""
import base64, gzip, json, pathlib, re, sys

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
SRC = ROOT / "site" / "index.html"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "site"

# Image uuid -> path under assets/. Named from each image's alt text and the
# heading above it. Fonts are not listed here: their names are derived from the
# @font-face rules that reference them, so no uuid needs transcribing by hand.
IMAGES = {
    "ab420f11-4015-46ab-8687-4197920c6693": "img/icon-doc.svg",
    "3de4db70-531e-4e2c-a351-5c44d3674a9a": "img/hero-illustrasjon.svg",
    "3695d1ec-f7d2-4812-a82a-ab4255549882": "img/diagram-hvordan-fungerer-det.svg",
    "aefbcf7e-bc8a-48f9-9240-2ee4d876f282": "img/diagram-data-inn.svg",
    "6764b53b-d327-44fb-9b44-36235001afe3": "img/diagram-komme-i-gang.svg",
    "56492148-a7c8-4e58-b469-7051a2e3d55c": "img/diagram-hva-tilbyr-entur.svg",
    "61062f0f-673c-4e39-9ce3-a4daf31e9948": "img/entur-logo.png",
    "b6199340-a186-4337-9b35-37f98f970d77": "img/reisedetaljer-siri.png",
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

    # Only meaningful now: until the inline <style> blocks were replaced above,
    # the font uuids still appeared in the template by construction.
    for uid in names:
        if uid in template:
            sys.exit(f"refusing: uuid {uid} still in html after rewrite")
        if uid in css:
            sys.exit(f"refusing: uuid {uid} still in css after rewrite")
    if "__bundler" in template:
        sys.exit("refusing: bundler scaffolding still present in html")

    (OUT / "index.html").write_text(template, encoding="utf-8")

    total = sum((OUT / "assets" / n).stat().st_size for n in names.values())
    print(f"assets   {len(names):>3} files  {total/1024:>9.1f} KiB")
    print(f"css              {len(css)/1024:>9.1f} KiB")
    print(f"js               {len(js)/1024:>9.1f} KiB")
    print(f"html             {len(template)/1024:>9.1f} KiB")


if __name__ == "__main__":
    main()
