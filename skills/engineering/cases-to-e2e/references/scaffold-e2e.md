# Scaffolding a Playwright project from nothing

Only after the user has agreed to it, and only once you have confirmed the repo
really has no E2E project (`find . -name 'playwright.config.*' -not -path
'*/node_modules/*'`). This is the shape to aim for; **adapt it to the repo
rather than imposing it** — a monorepo with its own conventions for packages,
scripts and env files wins over this sketch.

## Layout

```
<e2e-root>/
├── playwright.config.ts
├── package.json          # its own package when the repo is a monorepo
├── .env.example          # placeholders only — never a real credential
├── fixtures/
│   ├── index.ts          # test = base.extend({...}) — specs import from here
│   ├── env.ts            # typed env access, fails loudly on a missing required var
│   ├── pages/            # one page object per screen
│   └── utils/            # upload, download, wait-for-API, evidence helpers
├── helpers/              # pure functions: route builder, asset paths, parsers
├── assets/<feature>/     # fixture files + a README explaining each one
└── tests/<feature>/      # specs
```

Name the root whatever the repo's conventions suggest (`e2e/`, `tests/e2e/`,
`packages/e2e/`), and put the output directories in `.gitignore`.

## Decisions worth making explicitly

- **Auth.** A `setup` project that signs in once and saves `storageState`, with
  the authenticated project depending on it, beats logging in per test. Guard it
  so a missing credential skips rather than fails cryptically.
- **Base URL from the environment**, never hardcoded, so the same suite can run
  against a local stack and a deployed one.
- **`webServer` with `reuseExistingServer`** so the suite attaches to a dev
  server that is already up instead of fighting it for the port.
- **Locator strategy.** Decide up front — role + accessible name is the default;
  add `data-testid` only where the DOM offers nothing nameable, and say so.
- **What a missing fixture asset does.** Self-skip with a message naming the
  file is the friendly default, but then the run summary must be read for skips.
- **Where evidence lands.** A stable directory *outside* Playwright's
  `outputDir`, because Playwright wipes `outputDir` at the start of every run
  and last run's evidence would disappear. Add the JSON reporter alongside the
  HTML one, so an evidence exporter has a machine-readable result to read.

## Before declaring it done

Add the scripts the rest of the repo expects (`test`, `lint`, `check:types` or
their local names), wire the output directories into `.gitignore`, and run the
whole suite once from a clean checkout — a suite that only passes on the
author's machine is not set up yet.
