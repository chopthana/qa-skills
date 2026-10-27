# 1. Ship as a plugin marketplace, not a bespoke installer

## Context

The skills had to be installable on any machine and by agents other than Claude
Code. Three routes were tried: a bash symlink script, then a Node CLI published
through `npx github:…`, then each agent's own plugin commands.

## Decision

The repo **is** a marketplace: `.claude-plugin/marketplace.json` plus
`plugin.json` listing the skills it ships. Installation uses each agent's native
plugin commands; `npx skills` covers agents that have none. No installer of our
own.

## Consequences

- Nothing to maintain: version negotiation, caching and updates belong to each
  agent. Bumping `version` in `plugin.json` is what releases a change, so it
  has to happen in the same commit as the change.
- Managed installs run from a **copy of what is pushed**. Writing a skill means
  cloning and symlinking into `~/.agents/skills/` instead, so edits take effect
  without a push.
- A skill directory under `skills/<category>/<name>/` is the unit both the
  manifests and `gemini skills install --path` point at.
