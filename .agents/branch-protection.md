# Protecting `main`

What is wanted: **no force-push, no deletion, outsiders go through a PR, the
owner can bypass.**

## Server-side is unavailable while this repo is private

GitHub refuses both mechanisms on a private repo on a Free personal plan:

```text
POST /repos/ppthana/qa-skills/rulesets          403
PUT  /repos/ppthana/qa-skills/branches/main/protection   403
"Upgrade to GitHub Pro or make this repository public to enable this feature."
```

So it becomes available the moment **either** happens: the repo goes public, or
the account moves to GitHub Pro. The ruleset to apply is committed at
[`.github/rulesets/main.json`](../.github/rulesets/main.json) — deletion and
non-fast-forward blocked, PRs required with one approval, and
`RepositoryRole 5` (admin, i.e. the owner) as a bypass actor:

```bash
gh api -X POST repos/ppthana/qa-skills/rulesets --input .github/rulesets/main.json
gh api repos/ppthana/qa-skills/rulesets -q '.[] | "\(.id)  \(.name)  \(.enforcement)"'
```

## What is already true

- **Nobody outside can push.** GitHub requires collaborator access to push at
  all, and this repo has no collaborators. A public repo does not change that:
  an outsider can fork and open a PR, which never writes here. "Outsiders go
  through a PR" is enforced by access control, not by a rule.
- The realistic risk while private is therefore **our own** force-push or
  branch deletion, which is what the local hook below covers.

## The local hook

`.agents/hooks/pre-push` refuses exactly what the ruleset would: deleting
`main`, and any push to `main` that is not a fast-forward (force-push, or an
amend/rebase of commits already pushed).

```bash
ln -sf ../../.agents/hooks/pre-push .git/hooks/pre-push   # once per clone
```

Git never installs hooks from a repository by itself, so this is per clone and
is the reason the hook is committed rather than only living in `.git/`. It is a
seatbelt, not a lock: it runs on the machine doing the push, and
`PROTECT_MAIN=0 git push` overrides it deliberately. Anyone with push access who
has not installed it is unprotected — which is the gap only a server-side
ruleset closes.
