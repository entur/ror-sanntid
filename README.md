# ror-sanntid

Static site served at <https://sanntid.entur.no>. Plain HTML in `site/`, no
build step, published to GitHub Pages on every push to `main`.

## Layout

```
site/                  served verbatim
  index.html           the page; one very large file, see below
  404.html
.github/workflows/     ci (checks), pages (deploy), codeql
tools/check_site.py    tags, links, required elements
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

## site/index.html

2.75 MB, content embedded as a bundle that unpacks client-side. The payload sits
on two enormous lines, so diffs are unreadable and reformatters will mangle it.
`check_site.py` assumes nothing about its size or contents, so it can be edited
or replaced freely.
