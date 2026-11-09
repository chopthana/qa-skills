# Resuming an existing ledger

`<workspace>/progress.md` already exists. Before anything else, work out whose
it is and where it stopped. The expensive failure is re-dispatching slices that
are already written, then merging a double set.

## 1. Whose ledger is it?

Read the first line: `# testcase-sdd ledger — producer: … — sources: … — out: …`

- **Same sources and same deliverable** as this run → it is yours. Resume.
- **Different** → you are in another run's directory. Stop, get a fresh run slug
  from `scripts/tc-workspace`, and never write into this one.
- **No identity line** → treat the directory as untrusted: read the files to see
  what exists, write a new ledger with an identity line, and reconstruct the
  slice table from what is on disk.

## 2. Trust the disk over the ledger

The ledger says what you intended; the files say what happened. Reconcile per
slice:

| On disk | Ledger says | Where it is |
| --- | --- | --- |
| `slice-N-cases.json` + `slice-N-review.md`, review clean | complete | done — do not touch |
| cases + review, review not clean | in fix loop | resume the loop at the recorded round; if no round is recorded, start at round 1 |
| cases, no review | dispatched | dispatch the reviewer |
| brief only | dispatched | the author died or was never dispatched. Dispatch a fresh author on the existing brief |
| nothing | pending | normal dispatch |
| `merged.cases.json` newer than every slice file | merged | go to the final review |
| `merged.cases.json` older than some slice file | stale | re-run the merge before anything else |

A slice file that exists but is empty or unparseable counts as *brief only*.

## 3. Then

Rewrite the slice table in the ledger with the reconciled states, append
`Resumed: <date> — <n> complete, <m> outstanding`, and continue the loop from
§ 3 of SKILL.md. Do not re-survey: the inventory is already written, and a
second surveyor will renumber the item IDs that every existing brief and
`covers` list points at.

If the inventory is missing but slice files exist, reconstruct it from the briefs
rather than re-surveying — the IDs in the briefs are the contract.
