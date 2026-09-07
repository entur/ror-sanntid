# ror-sanntid

Static site served at <https://sanntid.entur.no>. Plain HTML in `site/`, no
build step, published to GitHub Pages on every push to `main`.

## Layout

```
site/                  served verbatim
  index.html           norsk, markup only
  en/index.html        english
  404.html
  assets/
    styles.css
    app.js             accordions, collapsible detail block
    fonts/             Nationale, 6 weights
    img/               diagrams per language, screenshots, icon and logo
.github/workflows/     ci (checks), pages (deploy), codeql
tools/
  check_site.py        tags, links, fragments, ids, css url(), required
                       elements, link-list parity between the two sections
  unbundle.py          re-import a Claude artifact bundle
```

## Local

```sh
python3 -m http.server -d site 8000
python3 tools/check_site.py
```

`404.html` only renders on Pages, not under `http.server`.

## Deploy

`pages.yml` runs the checks in a read-only job, then deploys from a second job
that holds the Pages credentials. `ci.yml` runs the same checks on pull requests.

The custom domain is bound by the repo's **Pages setting**, not by any file in
the repo: Pages ignores `CNAME` files when publishing from Actions. `pages.yml`
keeps the hostname in `SITE_DOMAIN` and fails if the live setting stops matching.

## Setup, still outstanding

Add a ruleset on `main` requiring the CI check and a CODEOWNERS review. Without
it `ci.yml` gates nothing and `CODEOWNERS` is inert.

The Pages source, the DNS record, the custom domain with HTTPS enforced and
`@entur/team-ruter-reiseplanlegger`'s admin rights are all in place.

## The two pages

`site/index.html` is Norwegian, `site/en/index.html` English. They share
`assets/`, including the fonts and the photographic screenshots; only the
diagrams exist per language, suffixed `-en`. The language switch in the header
is a pair of links, so it works without JavaScript and each language keeps its
own URL, canonical and `hreflang`.

The Claude export ships both languages in one document as `[data-lang-pane]`
blocks that a script shows and hides. `unbundle.py` splits them.

## Duplicated link lists

`#enturs-rolle` spells out 23 external links in prose panels and
`#dokumentasjon` repeats 21 of them in a bare index, on both pages. One URL
change is therefore four identical edits. `check_site.py` compares the two
lists per page and fails if they disagree, so a partial edit fails CI. The two
the prose keeps to itself are listed in its `PROSE_ONLY` set.

The links themselves are not fetched, so a URL that starts 404ing is not caught
by anything here.

## Markup

Markup only. CSS, JS, fonts and images are separate files under `site/assets/`,
so each caches independently and a text edit no longer re-ships 2.3 MB.

Content inside the accordions and the collapsible detail block ships expanded;
`app.js` collapses it on load. Without JavaScript it stays readable, findable
and linkable.

Formatted with prettier, and CI enforces it: run `npx prettier --write site/`
before pushing. The formatter also doubles as the markup validator, since
`check_site.py` parses with Python's lenient `HTMLParser` and will accept a
malformed tag that prettier rejects.

It started as a single self-unpacking Claude artifact bundle. `tools/unbundle.py`
does that conversion and is kept for re-importing a fresh bundle when the page
is redesigned in Claude:

```sh
cp "Sanntid - No-en.html" site/index.html
python3 tools/unbundle.py
```

Its uuid-to-filename map has to be updated for each new export. What it emits
still needs the head metadata, the skip link, `<main>`, img `width`/`height`,
the expanded-by-default markup and `npx prettier --write site/` applied by
hand; diff against the previous commit to see what to carry over. It is not
part of the build, and editing `site/` directly is the normal path.

## Known deviation

Pages cannot set `X-Content-Type-Options`, CSP or `X-Frame-Options`, which Entur
`security.md` requires, and serves a Let's Encrypt certificate rather than a
Google-managed one. Both are inherent to Pages. Worth clearing alongside the DNS
request.
