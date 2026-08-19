# ror-sanntid

Static site served at <https://sanntid.entur.no>. Plain HTML in `site/`, no
build step, published to GitHub Pages on every push to `main`.

## Layout

```
site/                  served verbatim
  index.html           markup only, 71 KB
  404.html
  assets/
    styles.css
    app.js             anchor scrolling, accordions
    fonts/             Nationale, 6 weights
    img/               8 diagrams, icon and logo
.github/workflows/     ci (checks), pages (deploy), codeql
tools/
  check_site.py        tags, links, css url(), required elements
  unbundle.py          re-import a Claude artifact bundle
```

## Local

```sh
python3 -m http.server -d site 8000
python3 tools/check_site.py
```

`404.html` only renders on Pages, not under `http.server`.

## Deploy

`pages.yml` checks, uploads `site/` and deploys. `ci.yml` runs the same checks
on pull requests.

The custom domain is bound by the repo's **Pages setting**, not by any file in
the repo: Pages ignores `CNAME` files when publishing from Actions. `pages.yml`
keeps the hostname in `SITE_DOMAIN` and fails if the live setting stops matching.

## Setup, still outstanding

1. Settings → Pages → Source: **GitHub Actions**
2. Ask `#talk-utviklerplattform` for `sanntid.entur.no. CNAME entur.github.io.`
3. Settings → Pages → Custom domain, then **Enforce HTTPS**
4. Grant `@entur/team-ruter-reiseplanlegger` admin on the repo

## site/index.html

Markup only. CSS, JS, fonts and images are separate files under `site/assets/`,
so each caches independently and a text edit no longer re-ships 2.3 MB. Formatted
with prettier, which CI does not enforce: run `npx prettier --write site/` if you
care.

It started as a single 2.75 MB self-unpacking Claude artifact bundle.
`tools/unbundle.py` did that conversion and is kept for re-importing a fresh
bundle if the page is redesigned in Claude. It is not part of the build; editing
`site/` directly is the normal path.

## Known deviation

Pages cannot set `X-Content-Type-Options`, CSP or `X-Frame-Options`, which Entur
`security.md` requires, and serves a Let's Encrypt certificate rather than a
Google-managed one. Both are inherent to Pages. Worth clearing alongside the DNS
request.
