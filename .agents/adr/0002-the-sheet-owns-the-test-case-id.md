# 2. The sheet owns the test-case ID

## Context

Converting QA workbooks into a repo's YAML tree needs an `id` per case. The
first version coined repo-side IDs from the directory names, keeping the
workbook's `TC ID` only in a comment. QA then had two numbering systems to
reconcile by hand, and every conversation about a case needed a translation
step.

## Decision

The workbook's `TC ID` is the case `id`, copied verbatim. Prefix, spelling and
numbering are not "improved". Where the sheet cannot supply a usable ID — none
given, one ID reused across rows, a spelling the schema rejects, a collision
with an existing ID — the agent **asks, with a concrete proposal**, and never
decides alone.

## Consequences

- Fixing the sheet beats diverging from it: after a sheet edit, re-scan and diff
  before touching YAML, because an edit can land off by a row.
- The report states identity as a count (`TC ID == id: 93/93`); that number is
  what a reviewer actually checks.
- `# Source:` above every case stays mandatory regardless, since the case schema
  is five fields and has nowhere else to record provenance.
