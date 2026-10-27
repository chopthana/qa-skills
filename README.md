# Chop's agent skills

Personal agent skills, straight from my `.agents` directory. Private on
purpose — some carry work-specific detail (internal UI labels, table names,
ticket numbers).

A `SKILL.md` here is plain Markdown with YAML frontmatter and no tool-specific
syntax, so these work with any agent that reads Agent Skills.

## Skills

| Skill | What it does |
| --- | --- |
| [`gen-test-cases-to-yaml`](skills/engineering/gen-test-cases-to-yaml/SKILL.md) | Batch-convert a whole sprint folder of QA test-case workbooks into a repo's own domain test-case YAML tree — translated to English, staged in one folder, reconciled row-by-row so nothing is dropped, imported in one pass. |

## Installation

This repo is **private**, so every route below needs GitHub access to it: be the
owner, or be added as a collaborator. The native plugin commands clone with your
own git credentials, so they work once you have access.

Pick **one** route per agent — installing two gives you every skill twice.

<details>
<summary><strong>Claude Code</strong></summary>

```bash
claude plugin marketplace add ppthana/qa-skills
claude plugin install chop-skills@ppthana
```

Updates itself. To pull a change by hand: `claude plugin update chop-skills`.

</details>

<details>
<summary><strong>Codex</strong></summary>

```bash
codex plugin marketplace add ppthana/qa-skills
codex plugin add chop-skills@ppthana
```

Updates at startup.

</details>

<details>
<summary><strong>GitHub Copilot</strong> (CLI and VS Code)</summary>

```bash
copilot plugin marketplace add ppthana/qa-skills
copilot plugin install chop-skills@ppthana
```

Then once, in `~/.copilot/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "ppthana": {
      "source": { "source": "github", "repo": "ppthana/qa-skills" },
      "autoUpdate": true
    }
  }
}
```

In VS Code: **Chat: Install Plugin From Source**, then
`https://github.com/ppthana/qa-skills`.

</details>

<details>
<summary><strong>Gemini CLI</strong> (manual updates)</summary>

```bash
gemini skills install https://github.com/ppthana/qa-skills.git --path skills/engineering
```

Re-run to update.

</details>

<details>
<summary><strong>Any other agent, or editable files</strong> (manual updates)</summary>

```bash
npx skills@latest add ppthana/qa-skills -a <agent>   # cursor, opencode, windsurf, amp, …
```

`npx skills` fetches through the public skills.sh service, so it is the one
route that will **not** reach this private repo. Until the repo is public, clone
and link instead:

```bash
git clone https://github.com/ppthana/qa-skills.git ~/Desktop/qa-skills
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

## Layout

```text
.agents/install-block.md   the canonical install wording — change it there first
.claude-plugin/
├── marketplace.json   catalog: marketplace `ppthana`, plugin source "./"
└── plugin.json        plugin `chop-skills`: version and the skills it ships
skills/<category>/<skill-name>/
├── SKILL.md           frontmatter (name + description) and the workflow
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

`gen-test-cases-to-yaml` needs Python 3 with `openpyxl` (reading .xlsx) and
`PyYAML`:

```bash
pip3 install --user openpyxl pyyaml
```

It also calls two scripts that live inside the people-admin repo
(`.agents/skills/testcase-to-domain/scripts/`), so run it from that repo's root
when converting for that project. Its own `scripts/` are self-contained.
