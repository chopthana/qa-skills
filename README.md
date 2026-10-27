# Chop's Claude skills

Personal [Agent Skills](https://docs.claude.com/en/docs/claude-code/skills) kept
on this machine and backed up here, packaged as a **Claude Code plugin
marketplace** so they install with two commands on any machine. Private on
purpose — some of them carry work-specific detail (internal UI labels, table
names, ticket numbers).

## Skills

| Skill | What it does |
| --- | --- |
| [`gen-test-cases-to-yaml`](skills/gen-test-cases-to-yaml/SKILL.md) | Batch-convert a whole sprint folder of QA test-case workbooks into the people-admin repo's domain test-case YAML — translated to English, staged in one folder, reconciled row-by-row so nothing is dropped, imported in one pass. |

## Install (recommended)

Works on any machine where `gh`/git can reach this private repo:

```bash
claude plugin marketplace add ppthana/Chop-thanakorn-skills
claude plugin install gen-test-cases-to-yaml@chop-thanakorn-skills
```

Then invoke with `/gen-test-cases-to-yaml`, or just describe the task — the
`description` in the skill's frontmatter is what Claude matches against.

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

## Install for editing a skill (dev machine)

While actively writing a skill, skip the plugin and symlink it instead, so every
save takes effect in the next session with no push/update round trip:

```bash
ln -sfn ~/Desktop/Chop-thanakorn-skills/skills/<skill-name> ~/.claude/skills/<skill-name>
```

Use one or the other, not both — the same skill name registered twice gets
loaded twice. `claude plugin uninstall <name>` before symlinking, and remove the
symlink before installing the plugin.

## Layout

```text
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
