# The canonical install block

One install story, one wording. `README.md` and anything else that tells someone
how to install must say **this** and nothing else. Change it here first, then
propagate.

## Managed installs first

Lead with routes that update themselves. Fall back to a manual route, labelled
"manual updates", only for agents that have none. A route counts as managed only
if it updates without the user running a command. Put any one-time opt-in beside
its install command. Never promise "instant".

Every managed route installs from this repo's own marketplace —
`.claude-plugin/marketplace.json` (named `chopthana`) and `plugin.json` (the
bundle `qa-skills`). Those routes reinstall only when `version` in
`plugin.json` changes, so **bump it in the same commit as any skill change**;
this repo has no release automation to do it.

| Agent | Route | Updates itself? |
| --- | --- | --- |
| Claude Code | `qa-skills@chopthana` | Yes, by default |
| Codex | `qa-skills@chopthana` | Yes, at startup |
| Copilot CLI / VS Code | `chopthana` marketplace | Yes, after a one-time `autoUpdate: true` |
| Gemini CLI | `gemini skills install` (copies) | No. Re-run the command |
| Everyone else | clone + symlink | No. `git pull` in the clone |

## Updating gets its own section

Someone who installed from the marketplace has no clone to `git pull`, so the
README must tell them the command that pulls a new `version` down. Collect those
in one `## Updating` table after the install blocks — never as a second command
block inside a `<details>`, which would break the one-block-per-agent rule. The
line under an install command says only *whether* the route updates itself; the
table says *how* to force it.

## This repo is private

That is the fact that makes our install story differ from a public skills repo,
and it must stay stated in the README:

- The **native plugin commands clone with the user's own git credentials**, so
  they work for anyone with access to the repo — owner or collaborator.
- **`npx skills@latest add` goes through the public skills.sh service**, which
  has no access to a private repo. It is listed for completeness and marked as
  not working here, with clone + symlink given as the fallback.

If the repo is ever made public, the `npx skills` route starts working and the
caveat comes out of the README — nothing else changes.

## Verified where?

Keep this honest; it is the difference between a README that works and one that
reads well.

- **Claude Code** — verified on this machine end to end: `marketplace add`,
  `install`, `plugin details` showing the skill and its `scripts/`.
- **Codex, Copilot, Gemini CLI** — wording taken from each tool's own
  documented commands and adapted to this repo. Those CLIs are not installed
  here, so nobody has run them against it. Do not upgrade this claim without
  running them.
- **clone + symlink into `~/.agents/skills/`** — verified on this machine; this
  is also the route to use while *writing* a skill, since the plugin routes run
  from a copy of what is pushed.
- **Update commands** — the Claude Code pair (`plugin marketplace update`, then
  `plugin update`) was run here. The Codex and Copilot ones are quoted from
  OpenAI's and GitHub's own CLI references; neither CLI is installed on this
  machine, so nobody has run them against this repo.

## Wording rules

- One command block per agent, inside a `<details>` block titled with the agent
  name. Nothing else between the summary and the command.
- Say what updates mean for that route on the line under the command, in one
  sentence — whether it updates itself, not how to force it. The command to
  force it belongs in the `## Updating` table.
- The invocation line goes once, after all the blocks — `/<skill-name>`, or just
  describe the task, because the frontmatter `description` is what the agent
  matches against.
- Say "Restart the agent, or reload its skills" once, at the end. Not per agent.
