# The review page's database

Three collections in the artifact's own `db`. Document ids are the TC ID with
every character outside `A-Za-z0-9_-.~:@+` replaced by `_` (db path segments
allow nothing else), so the real TC ID always travels in the body as well.

Read and write them with the `ArtifactData` tool, passing the artifact's URL.

## `cases` — one document per reviewed case

Written by the page when someone presses a verdict button or types in the box.

```json
{
  "tc_id": "SHIFT-WG-HRIS-EXPORT-004",
  "verdict": "pass | fix | ask",
  "note": "แก้เป็นอะไร / คำถามถึง BA",
  "reviewer_id": "u_...",
  "updated_at": "2026-11-13T08:30:00.000Z"
}
```

A case with no verdict has **no document** — clearing a verdict deletes it.
So "ยังไม่รีวิว" is the absence of a row, never `verdict: ""`.

`reviewer_id` is the opaque id from the `user` capability, never a name: names
differ per viewer and go stale. The page resolves them for display with
`user.profiles(ids)`; `ArtifactData`'s `action: "profiles"` does the same from
a session.

## `global_fixes` — findings that hit the whole set

Written from the **แก้ทั้งชุด** box above the table. Document ids are minted by
the page (`g` + a base-36 timestamp), not TC IDs.

```json
{
  "text": "step 4 ทุกเคส เปลี่ยนเป็น Click icon view ของกระดานนั้นบนตาราง",
  "by": "u_...",
  "created_at": "2026-11-13T09:00:00.000Z"
}
```

One entry usually becomes dozens of cell edits. Expand it against the extracted
`review.json` — never against a guess at which cases are affected — and report
the count per entry. Entries are deleted from the page once they are applied
and the reviewer is happy; the skill does not delete them on its own.

## `meta` — one document, `submission`

Written when **ส่งกลับเพื่อแก้ไข** is pressed.

```json
{
  "batch": 1,
  "submitted_at": "2026-11-13T09:00:00.000Z",
  "by": "u_...",
  "count_pass": 41,
  "count_fix": 9,
  "count_ask": 3,
  "count_global": 2
}
```

`batch` counts up by one per submission. Record the one you applied with
`review_state.py set --batch <n>` so a later run can tell a fresh submission
from one already handled.

## `applied` — one document per case Claude has already changed

Written from a session after `apply_review.py` succeeds, with `ArtifactData`
`action: "batch"`. The page shows it as "✔ แก้แล้ว" with the new text, and
the **แก้แล้ว** filter lists them.

```json
{
  "tc_id": "SHIFT-WG-HRIS-EXPORT-004",
  "field": "expected",
  "before": "…the cell as it was…",
  "after": "…the cell as it is now…",
  "applied_at": "2026-11-13T09:05:00+0700"
}
```

`apply_review.py --applied-out` writes exactly these fields (plus `row` and
`changed`, which the page ignores).

## Access

Declared as `{"db": {}, "user": {"scopes": ["profile"]}}` — no `rules`.
The defaults give what this page needs:

| who | can |
| --- | --- |
| the owner (QA) | read and write |
| Contributor | read and write |
| Viewer, Commenter, outside viewer | read only |

So a BA or PO invited as Viewer gets the page read-only with no extra
configuration. The page gates its own controls on `user.can("data.write")`
rather than waiting for a write to fail.
