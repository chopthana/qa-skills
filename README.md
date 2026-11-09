# Chop's agent skills

Personal agent skills, straight from my `.agents` directory. Private on
purpose — some carry work-specific detail (internal UI labels, table names,
ticket numbers).

A `SKILL.md` here is plain Markdown with YAML frontmatter and no tool-specific
syntax, so these work with any agent that reads Agent Skills.

## Skills

Seven skills covering one QA workflow, in the order it runs.

**Writing cases**

| Skill | What it does |
| --- | --- |
| [`create-test-cases-spec`](skills/engineering/create-test-cases-spec/SKILL.md) | A UI screenshot plus a Jira/PRD spec becomes reviewed test cases, section by section, each step confirmed with you before the next — delivered as text ready to paste into Excel. |
| [`spec-prototype-to-testcases`](skills/engineering/spec-prototype-to-testcases/SKILL.md) | A ticket plus its published design prototype becomes a workbook in your team's own template. Decompiles the prototype bundle for the strings as built, compares them against the spec, and raises every disagreement as a question instead of picking a side. |
| [`subagent-driven-testcases`](skills/engineering/subagent-driven-testcases/SKILL.md) | Runs a bulk job as a controller plus fan-out subagents: one coverage inventory, disjoint slices, an author per slice and a reviewer after it, then a merge that owns the IDs. Drives whichever skill above writes the cases — it writes none itself. Automating a suite is its second branch, with coverage reported per case in buckets (green / automated / parked / missing) instead of one flattering percentage. |

**Checking what exists**

| Skill | What it does |
| --- | --- |
| [`testcase-coverage-audit`](skills/engineering/testcase-coverage-audit/SKILL.md) | Audits a set already written: the cases that cannot be executed as written (an expected result that contradicts itself, two data values in one row, an assertion the steps never reach) and the cases missing because nobody traced the screen's reachable states. |
| [`design-handoff-check`](skills/engineering/design-handoff-check/SKILL.md) | Reads a published design handoff, compares it against the running app and the cases you already have, and sorts the result into covered / gap / mismatch / question / not-prototyped. |
| [`ui-explore`](skills/engineering/ui-explore/SKILL.md) | Plays the app in a browser the way a real person who tries things does — every control, edge values, orders nobody planned for — and reports findings with repro steps, not specs. |

**Moving cases around**

| Skill | What it does |
| --- | --- |
| [`gen-test-cases-to-yaml`](skills/engineering/gen-test-cases-to-yaml/SKILL.md) | Batch-converts a whole sprint folder of workbooks into a repo's own domain test-case YAML tree — translated to English, staged in one folder, reconciled row-by-row so nothing is dropped, imported in one pass. Re-runs convert only the delta. |

## Installation

This repo is **private**, so every route below needs GitHub access to it: be the
owner, or be added as a collaborator. The native plugin commands clone with your
own git credentials, so they work once you have access.

Pick **one** route per agent — installing two gives you every skill twice.

<details>
<summary><strong>Claude Code</strong></summary>

```bash
claude plugin marketplace add chopthana/qa-skills
claude plugin install qa-skills@chopthana
```

Updates itself.

</details>

<details>
<summary><strong>Codex</strong></summary>

```bash
codex plugin marketplace add chopthana/qa-skills
codex plugin add qa-skills@chopthana
```

Updates at startup.

</details>

<details>
<summary><strong>GitHub Copilot</strong> (CLI and VS Code)</summary>

```bash
copilot plugin marketplace add chopthana/qa-skills
copilot plugin install qa-skills@chopthana
```

Then once, in `~/.copilot/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "chopthana": {
      "source": { "source": "github", "repo": "chopthana/qa-skills" },
      "autoUpdate": true
    }
  }
}
```

In VS Code: **Chat: Install Plugin From Source**, then
`https://github.com/chopthana/qa-skills`.

</details>

<details>
<summary><strong>Gemini CLI</strong> (manual updates)</summary>

```bash
gemini skills install https://github.com/chopthana/qa-skills.git --path skills/engineering
```

Re-run to update.

</details>

<details>
<summary><strong>Any other agent, or editable files</strong> (manual updates)</summary>

```bash
npx skills@latest add chopthana/qa-skills -a <agent>   # cursor, opencode, windsurf, amp, …
```

`npx skills` fetches through the public skills.sh service, so it is the one
route that will **not** reach this private repo. Until the repo is public, clone
and link instead:

```bash
git clone https://github.com/chopthana/qa-skills.git ~/Desktop/qa-skills
ln -sfn ~/Desktop/qa-skills/skills/engineering/gen-test-cases-to-yaml \
        ~/.agents/skills/gen-test-cases-to-yaml
```

`~/.agents/skills/` is the shared Agent Skills directory that Cursor, Gemini CLI,
opencode and others read. A symlink also means edits in the clone take effect
immediately, which is what you want while writing a skill — the plugin routes
above run from a copy of what is **pushed**.

</details>

Then invoke with `/gen-test-cases-to-yaml`, or just describe the task — the
`description` in the skill's frontmatter is what the agent matches against.
Restart the agent, or reload its skills, after installing.

## Updating

A new skill, or a change to one, reaches you only when `version` in
`plugin.json` moves — the managed routes compare that, not the commit. None of
these commands needs a clone of this repo.

| Agent | Pull the change |
| --- | --- |
| Claude Code | `claude plugin marketplace update chopthana`, then `claude plugin update qa-skills` |
| Codex | `codex plugin marketplace upgrade chopthana` |
| Copilot CLI / VS Code | `copilot plugin marketplace update chopthana`, then `copilot plugin update qa-skills` |
| Gemini CLI | re-run the `gemini skills install` command above |
| clone + symlink | `git pull` in the clone |

Claude Code and Codex pick a change up on their own too; Copilot does once
`autoUpdate` is set as above. The commands are for when you would rather not
wait. Restart the agent afterwards — an update is applied on the next start.

Where there are two commands, the first refreshes this repo's catalog and the
second installs the version that catalog now names — refreshing alone changes
nothing you run. Codex documents no per-plugin command, so there the refresh is
the whole step.

If the **plugin name or the marketplace name** ever changes, no update command
helps, because the identifier your install is registered under no longer exists.
Remove it and install again with the new name.

## Layout

```text
.agents/install-block.md   the canonical install wording — change it there first
.claude-plugin/
├── marketplace.json   catalog: marketplace `chopthana`, plugin source "./"
└── plugin.json        plugin `qa-skills`: version and the skills it ships
skills/<category>/<skill-name>/
├── SKILL.md           frontmatter (name + description) and the workflow
├── references/        reference the SKILL.md points at, loaded on demand
└── scripts/           helpers the SKILL.md calls
```

Adding a skill: drop it under `skills/<category>/`, add its path to
`plugin.json`'s `skills` array, bump `version` (managed installs only reinstall
when it changes), push. Validate first:

```bash
claude plugin validate .
```

Its LICENSE and icon findings only apply to submitting a plugin to Anthropic's
public directory — irrelevant for a private personal marketplace.

A skill the whole team should have belongs in that project repo's own
`.agents/skills/` instead of here.

## Requirements

Python 3 throughout. The skills that read or write `.xlsx` —
`gen-test-cases-to-yaml`, `spec-prototype-to-testcases`,
`testcase-coverage-audit` — need `openpyxl`, and `gen-test-cases-to-yaml` also
needs `PyYAML`:

```bash
pip3 install --user openpyxl pyyaml
```

`subagent-driven-testcases` and `spec-prototype-to-testcases`'s prototype
reader are stdlib only. Every `scripts/` directory is self-contained: no skill
here calls code from another repo.

Two skills need more than Python. `subagent-driven-testcases` needs an agent
that can dispatch subagents, plus whichever **producer** skill writes the cases
for that run — the producer's own requirements then apply. `ui-explore` and the
app-comparison half of `design-handoff-check` need a browser the agent can
drive.

**What you supply per run, because no skill here hardcodes it:** the prototype
or handoff base URL (`spec-prototype-to-testcases` reads `PROTOTYPE_BASE_URL`
or `--base` and ships with no default host), your team's workbook template and
its naming convention, the repo's test-case root, and the TC ID family already
in use. Each skill discovers or asks; see [ADR 3](.agents/adr/0003-skills-carry-no-project-specific-paths.md).
