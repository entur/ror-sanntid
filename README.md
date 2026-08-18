# ror-sanntid

Static site published to <https://sanntid.entur.no> from `site/`.

No build step in CI: `site/` is uploaded and served verbatim. `site/index.html`
is a generated bundle produced elsewhere and committed here — see
[Where index.html comes from](#where-indexhtml-comes-from).

## Layout

```
site/                     uploaded verbatim as the Pages artifact
  index.html              generated bundle; do not hand-edit
  404.html
.github/workflows/
  ci.yml                  checks on every PR and push
  pages.yml               checks, then deploys to Pages
  codeql.yml              org-required code scanning
tools/
  check_site.py           HTML and bundle-integrity checks
```

## Local development

Nothing to install. Preview with the standard library:

```sh
python3 -m http.server -d site 8000   # http://localhost:8000
python3 tools/check_site.py           # same checks CI runs
```

`404.html` is only served by Pages, not by `http.server`.

## Workflows

| Workflow | Trigger | Does |
|---|---|---|
| `ci.yml` | every PR and push to `main` | runs `check_site.py` |
| `pages.yml` | push to `main` touching `site/` or the workflow itself, or manual | checks, uploads `site/`, deploys, asserts the domain |
| `codeql.yml` | PR, push to `main`, weekly | code scanning |

`ci.yml` has no path filter on purpose: a path-filtered required status check
never reports on PRs that miss the filter, which wedges the merge button.
`pages.yml` only runs on `main`, so it gates nothing on a PR — `ci.yml` is what
does. `pages.yml` re-runs the same check itself, because the two workflows react
to the same push with no ordering between them, and only the copy inside the
deploy job runs before the upload.

Deployments queue rather than cancel, so a merge train cannot drop the last push.

## How the custom domain is bound

By the repo's Pages setting, and nothing else. Publishing from an Actions
workflow, GitHub ignores any `CNAME` file in the artifact — the sibling repo
`ror-dependency-dashboard` serves on its custom domain with no such file
anywhere in its tree.

That setting lives outside git, so `pages.yml` holds the intended hostname in
`SITE_DOMAIN` and asserts after each deploy that the live setting still matches:
a warning while unset, a failure if someone changes it. A deploy cannot clobber
the domain.

## No Terraform, no GCP

Nothing here is a GCP resource, so there is nothing to Terraform and no
`.entur/` manifest to register — that manifest exists to wire GCP workload
identity and dev/tst/prd projects, and `github-pages` is a GitHub-native
environment needing neither. The only real infrastructure is one DNS record.

## One-time setup

### 1. Enable Pages

Settings → Pages → Source: **GitHub Actions**.

That is the whole step. The repo is public, so the site is public and there is no
Pages visibility setting to choose — the separate visibility dropdown only appears
on private and internal repos. (The sibling `ror-dependency-dashboard` is internal
and does have one, set to private, which is why it login-walls visitors. This repo
will not.)

Do this before the first push to `main`, though `pages.yml` runs
`actions/configure-pages` with `enablement: true` so a fresh repo self-heals if
you forget.

### 2. Request the DNS record (team-plattform)

Ask in `#talk-utviklerplattform` for:

```
sanntid.entur.no.   CNAME   entur.github.io.
```

There is precedent: `ror-dependency-dashboard.entur.org` is already a `CNAME` to
`entur.github.io`, so this is a request the platform team has granted before.
Two differences worth naming so nobody is surprised later:

- That precedent is on `entur.org`; this asks for `entur.no`.
- Pages serves a GitHub-issued Let's Encrypt certificate, not the Google-managed
  cert the GKE golden path uses. The sibling already runs this way.

Worth adding to the same ticket: a `_github-pages-challenge-entur` TXT record.
Verification is **not** required — `entur.org` has none today — but it closes the
subdomain-takeover window described under *Changing the domain*, and costs
nothing while a request is already open.

### 3. Attach the domain

Once the CNAME resolves, Settings → Pages → Custom domain → `sanntid.entur.no`,
then tick **Enforce HTTPS** after the certificate is issued (usually minutes, up
to an hour). Until this is done, `pages.yml` warns on each deploy that no custom
domain is set.

### 4. Give the team ownership

Grant `@entur/team-ruter-reiseplanlegger` admin on the repo. `CODEOWNERS` already
names them, but that only assigns review — without the grant the repo has no
owning team and is routable only to an individual.

## Changing the domain

In order, because the first step has a lead time and the last is the dangerous one:

1. Request the **new** record from team-plattform.
2. Update `SITE_DOMAIN` in `.github/workflows/pages.yml` and the repo Pages
   setting together.
3. Request **removal** of the old `sanntid.entur.no CNAME entur.github.io.`

Step 3 is the one nothing in the repo will remind you about. A record left
pointing at `entur.github.io` after this repo stops claiming the hostname is
exactly GitHub's documented subdomain-takeover case: another org can attach the
name to their own Pages site.

## Deviations from Entur standards

Recorded here so they are a decision rather than an oversight. Worth clearing in
`#talk-utviklerplattform` alongside the DNS request.

- **TLS is GitHub-issued Let's Encrypt**, not Google-managed. Inherent to Pages;
  the golden path would require running this as a container on GKE.
- **Security headers cannot be set.** `security.md` asks for
  `X-Content-Type-Options: nosniff`, a CSP and `X-Frame-Options`; Pages sends
  none and offers no mechanism to add them. `<meta http-equiv>` cannot supply
  `nosniff` and `frame-ancestors` is ignored in meta CSP. HSTS is already
  satisfied. The exposure is thin — a static page with no auth, cookies, forms
  or user input — but it is a real gap, not a satisfied requirement.

## The site is public

The repo is public and Pages will serve `sanntid.entur.no` to anyone. Most of what
`site/index.html` links to is already public — `developer.entur.no`, `api.entur.io`,
`data.entur.no`. A few targets are not:

| Host | Links |
|---|---|
| `entur.atlassian.net` | 8 |
| `data-quality.entur.no` | 3 |
| `avvik.entur.org` | 2 |
| `vehicle-map.entur.org` | 2 |
| `realtime-archive.entur.org` | 2 |

Those pages require authentication, so this is not a data leak — but an external
reader sees links they cannot open, and the URLs themselves reveal some internal
tooling structure. Worth a glance before launch to confirm each one is meant to be
advertised publicly. Not a blocker, and nothing to change in the pipeline.

## Where index.html comes from

> **TODO — only the author can fill this in.** `site/index.html` is a 2.75 MB
> generated bundle that unpacks itself client-side. Nothing in the file records
> its generator, version or source. Name the source of truth and the exact
> command that regenerates it, so this is not a one-person dependency.

Do not hand-edit or reformat `site/index.html`. `check_site.py` asserts it stays
above 100 KB and still contains its `__bundler/manifest` and
`__bundler/template` markers, which catches truncation and whole-file loss but
not a bad regeneration.
