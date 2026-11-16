# The review page's database

Five collections in the artifact's own `db`. Document ids are the TC ID with
every character outside `A-Za-z0-9_-.~:@+` replaced by `_` (db path segments
allow nothing else), so the real TC ID always travels in the body as well.

Read and write them with the `ArtifactData` tool, passing the artifact's URL.

## `cases` — one document per reviewed case

Written by the page when someone presses a verdict button or types in the box.

```json
{
  "tc_id": "FEATURE-AREA-004",
  "verdict": "pass | fix",
  "note": "แก้เป็นอะไร / คำถามถึง BA",
  "reviewer_id": "u_...",
  "updated_at": "2026-11-13T08:30:00.000Z"
}
```

A case with no verdict has **no document** — clearing a verdict deletes it.
So "ยังไม่รีวิว" is the absence of a row, never `verdict: ""`.

The page counts each case in exactly one chip, deciding in the order verdict →
open question → added → changed → ยังไม่รีวิว, so the counts partition the set
and every chip but ผ่าน / แก้ counts down to zero as the round goes. That is
why a verdict is what empties `questions`, `applied` and `added` from the
reviewer's point of view, while the documents themselves stay for the badge
and the before/after.

What a chip *shows* is deliberately stickier than what it counts. A row stays
listed until its chip is pressed again, so pressing a verdict never pulls the
comment box out from under the reviewer, and **มีคำถาม** lists every case with
a question whatever its verdict, because that row is where the answer is
typed.

**`--apply` clears the verdicts it answered.** A `fix` whose edit has landed
is a spent instruction: leaving it makes ยังไม่รีวิว read 0 while the whole
batch is in fact waiting to be looked at again. Delete those documents once
the edits are in the workbook, after copying each note into that case's
`applied.asked`, and the next round opens with ยังไม่รีวิว equal to แก้แล้ว.

`reviewer_id` is the opaque id from the `user` capability, never a name: names
differ per viewer and go stale. The page resolves them for display with
`user.profiles(ids)`; `ArtifactData`'s `action: "profiles"` does the same from
a session.

## `questions` — what the set is waiting on BA for

One document per case with an open question, id = the slugged TC ID. Written
from a session when a review turns up something only BA or PO can settle, and
read back once they have.

```json
{
  "tc_id": "FEATURE-AREA-013",
  "text": "…the question, with the answer options spelled out…",
  "by": "u_...",
  "created_at": "2026-11-16T04:00:00.000Z"
}
```

A question is **not** a verdict, but a verdict is how it ends. The document
holds only the question; BA's answer arrives as **แก้** plus a note, or as
**ผ่าน**, in that case's `cases` document — one place to write, and the same
place every other answer in the review already goes. The **มีคำถาม** chip
counts the cases that carry a question and no verdict yet, so it empties as
the meeting works down the list, and lists them all either way, so the answer
can still be typed — and corrected — next to the question it answers.

Write `text` with the options in it, not just the question, and name the cases
an answer would move. Once the verdict is applied to the workbook, delete the
question document — a resolved question that stays becomes noise next round.

## `global_fixes` — findings that hit the whole set

Written from the **แก้ทั้งชุด** box above the table. Document ids are minted by
the page (`g` + a base-36 timestamp), not TC IDs.

```json
{
  "text": "<สิ่งที่ต้องแก้เหมือนกันทุกเคส หนึ่งประโยค>",
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
  "count_question": 3,
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
  "tc_id": "FEATURE-AREA-004",
  "kind": "edit",
  "fields": [
    {"field": "expected", "before": "…the cell as it was…", "after": "…as it is now…"},
    {"field": "steps", "before": "…", "after": "…"}
  ],
  "field": "expected, steps",
  "asked": "…the note that asked for this change…",
  "before": "…the cell as it was…",
  "after": "…the cell as it is now…",
  "applied_at": "2026-11-13T09:05:00+0700"
}
```

`fields` is what the page renders: each changed cell's old text sits under the
new one, in that cell's own column, so the next round judges the change rather
than the result alone. One case usually changes several cells, which is why it
is a list; `field` / `before` / `after` repeat the most substantive one so a
page built before `fields` existed still shows something.

`asked` is what the reviewer wrote that produced the change — their own note,
or the `global_fixes` sentence when the case was swept up by one. It is the
third side of the comparison the page shows: what was asked, what the cell
used to say, what it says now. It is also where that note survives, since the
verdict document it came from is deleted.

`kind` is `"edit"`, or `"add"` for a case the round appended — those have no
`before` to show, so the page gives them the **เพิ่มใหม่** chip and an
✚ badge instead of a comparison. `apply_review.py` also emits
`kind: "remove"`; that one is for the chat report, never for the db, since the
case it names is gone.

`apply_review.py --applied-out` writes exactly this, one object per case.

## When a case is removed and the set is renumbered

Document ids are TC IDs, so a renumber moves every document after the gap.
`apply_review.py --renumber-out` writes the map that does it:

```json
{"removed": ["FEATURE-AREA-032"],
 "renamed": {"FEATURE-AREA-033": "FEATURE-AREA-032", "…": "…"},
 "dangling_refs": ["เคส 032"]}
```

Apply it to `cases` and to `applied`, lowest new id first so each write lands
before its source is overwritten, then delete the highest old id — it has no
case left to describe. In `cases`, skip the documents whose verdict and note
come out the same: across a long run of `pass` the shift changes nothing a
reader can see, and a 40-case renumber becomes a dozen writes instead of
eighty. The one thing left stale is the `tc_id` field inside those skipped
documents; the page keys off the document id and a `pass` carries no
instruction, so nothing reads it.

`dangling_refs` is not a database matter — it is the sentences in the workbook
that still point at the case that went. Report them.

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
