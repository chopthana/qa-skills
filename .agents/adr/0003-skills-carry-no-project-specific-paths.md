# 3. Skills carry no project-specific paths

## Context

The first version of `gen-test-cases-to-yaml` hardcoded one employer's
directory (`docs/test-cases/domain/`), its domain/feature vocabulary and its ID
prefixes. It worked there and nowhere else, and the detail made the repo
unpublishable.

## Decision

A skill discovers the target repo's conventions at run time: the root it keeps
test cases in (`$ROOT`), that root's own `README.md`, the domains and features
already present, and the ID families in use. `$ROOT/README.md` outranks the
skill. Anything specific to one codebase appears only inside a block marked
**Worked example**, phrased as one repo's answer rather than the rule.

## Consequences

- Every skill gains a discovery step before it plans anything.
- Worked examples use invented, publishable data — no internal table names,
  ticket keys, screen names or customer data.
- Helper scripts take the same line: the issue-key pattern is a generic
  tracker-style key with `--ticket-pattern` to override, not one team's prefix.
