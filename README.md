# Chop's Claude skills

Personal [Agent Skills](https://docs.claude.com/en/docs/claude-code/skills) kept
on this machine and backed up here. Private on purpose — some of them carry
work-specific detail (internal UI labels, table names, ticket numbers).

## Skills

| Skill | What it does |
| --- | --- |
| [`gen-test-cases-to-yaml`](skills/gen-test-cases-to-yaml/SKILL.md) | Batch-convert a whole sprint folder of QA test-case workbooks into the people-admin repo's domain test-case YAML — translated to English, staged in one folder, reconciled row-by-row so nothing is dropped, imported in one pass. |

## Layout

```text
skills/<skill-name>/
├── SKILL.md          frontmatter (name + description) and the workflow
└── scripts/          helpers the SKILL.md calls
```

## Install on a machine

Skills load from `~/.claude/skills/`. Symlink rather than copy, so editing in
either place is the same file and `git status` here stays honest:

```bash
git clone git@github.com:ppthana/Chop-thanakorn-skills.git ~/Desktop/Chop-thanakorn-skills
ln -sfn ~/Desktop/Chop-thanakorn-skills/skills/gen-test-cases-to-yaml ~/.claude/skills/gen-test-cases-to-yaml
```

Being under `~/.claude/skills/` makes a skill available in **every** project on
the machine, and it is never committed into a work repo. A skill that the whole
team should have belongs in that repo's own `.agents/skills/` instead.

Invoke one with `/<skill-name>`, or just describe the task — the `description`
in the frontmatter is what Claude matches against.

## Requirements

`gen-test-cases-to-yaml` needs Python 3 with `openpyxl` (reading .xlsx) and
`PyYAML`:

```bash
pip3 install --user openpyxl pyyaml
```

It also calls two scripts that live inside the people-admin repo
(`.agents/skills/testcase-to-domain/scripts/`), so run it from that repo's root
when converting for that project. Its own `scripts/` are self-contained.
