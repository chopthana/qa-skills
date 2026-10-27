# Chop's agent skills

Personal [Agent Skills](https://docs.claude.com/en/docs/claude-code/skills) kept
on this machine and backed up here. Private on purpose — some of them carry
work-specific detail (internal UI labels, table names, ticket numbers).

A `SKILL.md` is plain Markdown with YAML frontmatter and no tool-specific
syntax, so these work with **any AI tool that reads Agent Skills** — Claude
Code, Codex, Cursor, Gemini CLI, opencode and others. Two install routes below:
`install.sh` for any tool, or the Claude Code plugin marketplace.

## Skills

| Skill | What it does |
| --- | --- |
| [`gen-test-cases-to-yaml`](skills/gen-test-cases-to-yaml/SKILL.md) | Batch-convert a whole sprint folder of QA test-case workbooks into a repo's own domain test-case YAML tree — translated to English, staged in one folder, reconciled row-by-row so nothing is dropped, imported in one pass. |

## Install — any AI tool

```bash
git clone https://github.com/ppthana/Chop-thanakorn-skills.git ~/Desktop/Chop-thanakorn-skills
cd ~/Desktop/Chop-thanakorn-skills
./install.sh --list     # show what it would do, change nothing
./install.sh            # do it
```

It symlinks each skill into the skill directories that exist on the machine:

| Directory | Read by |
| --- | --- |
| `~/.agents/skills/` | the harness-neutral convention — Codex, Cursor, Gemini CLI, opencode, and anything else that reads Agent Skills |
| `~/.claude/skills/` | Claude Code |

Symlinks, not copies: every tool reads the same file, and `git status` here stays
truthful. The script is idempotent, never overwrites anything it did not create,
takes skill names to install a subset, and `--uninstall` removes only links that
point into this repo.

A tool that reads a single instructions file instead of a skills directory
(`AGENTS.md`, `GEMINI.md`, `.cursorrules`) needs a pointer rather than a link —
add this to that file yourself:

```text
When a task matches a skill under ~/.agents/skills/, read that SKILL.md first
and follow it.
```

## Install — Claude Code plugin

Claude Code can install straight from this repo, with versioning and updates:

```bash
claude plugin marketplace add ppthana/Chop-thanakorn-skills
claude plugin install gen-test-cases-to-yaml@chop-thanakorn-skills
```

Then invoke with `/gen-test-cases-to-yaml`, or just describe the task — the
`description` in the skill's frontmatter is what the agent matches against.

Pick one route per skill, not both: the same skill name registered twice gets
loaded twice. `install.sh` detects an installed plugin and skips the Claude
symlink for you.

Housekeeping:

```bash
claude plugin list                       # what is installed
claude plugin details gen-test-cases-to-yaml@chop-thanakorn-skills
claude plugin update gen-test-cases-to-yaml   # after pushing a change here
claude plugin uninstall gen-test-cases-to-yaml
claude plugin marketplace remove chop-thanakorn-skills
```

An installed plugin runs from `~/.claude/plugins/cache/`, i.e. a copy of what is
**pushed**. Editing the working copy here changes nothing until you commit, push
and `claude plugin update`.

## Writing a skill

While actively editing one, use `install.sh` rather than the plugin: it links to
the working copy, so every save takes effect in the next session with no
commit/push/update round trip. The plugin route runs from a copy of what is
**pushed**.

## Layout

```text
install.sh             links skills into every skill dir on the machine
.claude-plugin/
├── marketplace.json   catalog: this repo as a marketplace, plugin source "./"
└── plugin.json        the plugin: version, metadata, which skills it ships
skills/<skill-name>/
├── SKILL.md           frontmatter (name + description) and the workflow
└── scripts/           helpers the SKILL.md calls
```

Adding another skill: drop it in `skills/`, list it in `plugin.json`'s `skills`
array (one plugin shipping several skills) or add a second entry to
`marketplace.json`'s `plugins` (separate plugins, installed independently), bump
the version, push. Validate before pushing:

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
