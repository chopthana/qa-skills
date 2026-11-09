# The inventory

One file, written once, by one surveyor subagent: `<workspace>/inventory.md`.
Everything downstream is cut from it, and the final review is scored against it.

An inventory item is **one testable obligation** — not a paragraph of the spec,
not a screen. If an item would take three unrelated cases to cover, it is three
items.

## Item IDs

| Prefix | What it marks |
| --- | --- |
| `AC-` | an acceptance criterion from the ticket/PRD, numbered as the ticket numbers it |
| `FR-` | a field rule: required, format, length, range, uniqueness scope, default, trim |
| `ST-` | a screen state: empty, loading, error, no-results, partial, over-limit |
| `FL-` | a flow that exists: create, edit, delete, search, export, cancel-midway |
| `W-` | a user-visible string that must be asserted somewhere: label, button, message, column header, option, empty-state heading *and* its sub-text |
| `NF-` | a non-functional obligation worth a case: permission, audit trail, pagination limit |

IDs are stable for the run. Never renumber them — briefs, `covers` lists,
reviews, the ledger and `coverage.md` all point at them.

## Format

`scripts/merge_slices.py` reads item IDs out of this file, so each item is one
table row whose **first cell is the ID**. Everything else is for humans and for
the briefs.

```markdown
# Inventory — <feature> (<date>)

sources: <ticket/PRD ref> · <prototype or screenshot ref> · <code ref if read>

## Field rules — Promo code form

| ID | Obligation | Exact values | Source | Conflict |
| --- | --- | --- | --- | --- |
| `FR-code-required` | Code cannot be submitted empty | message: "กรุณาระบุรหัสโปรโมชัน" | AC-2 | — |
| `FR-code-length` | Code is at most 12 characters | input caps at 12; no message | AC-2 | spec says 16 — ⚠️ Q1 |
| `FR-code-unique` | Code is unique per branch, not globally | message: "รหัสนี้มีอยู่แล้วในสาขานี้" | AC-4 | — |

## States — Promo code list

| ID | State | Exact values | Source | Conflict |
| --- | --- | --- | --- | --- |
| `ST-empty` | No promo codes yet | heading "ไม่พบข้อมูล", sub-text "โปรดตรวจสอบรายละเอียดการค้นหา" | prototype | not in spec — ⚠️ Q2 |

## Strings

| ID | Where | Exact text |
| --- | --- | --- |
| `W-btn-save` | primary button, create form | "บันทึก" |
| `W-col-headers` | list table | "รหัส" · "ชื่อโปรโมชัน" · "สาขา" · "สถานะ" |
```

> **Worked example** — the table above is invented. A real run's inventory
> carries that feature's own fields, its own messages, and its own ticket's AC
> numbering.

## Rules the surveyor follows

- **Exact values are the point.** An item whose "Exact values" cell says
  "an error message" is useless: the author will invent one. Go and get the
  string — from the spec, the prototype bundle, the screenshot, the code — or
  write `not found in sources` and raise it as a question.
- **Every user-visible string on every screen in scope gets a `W-` item.** This
  is the coverage nobody writes and the typo nobody catches.
- **Conflicts are recorded, never resolved.** The `Conflict` cell names both
  sides and gets a question number. The surveyor does not decide which wins.
- **Scope is the ticket.** A flow the sources show but the ticket does not ask
  for is an `FL-` item marked `out of scope — question`, not an obligation.
- **Typos are findings, not corrections.** A string that reads wrong is copied
  as built into "Exact values", with the suspicion in `Conflict`.

## Surveyor dispatch

Give it: the sources (paths, URLs, pasted text), the producer's SKILL.md path
if the producer owns a way of reading the sources (a prototype decompiler, a
string dumper), this file's path, and the output path. Capable model.

It returns counts only:

```text
items: <n> total — AC <a>, FR <b>, ST <c>, FL <d>, W <e>, NF <f>
conflicts: <n> (Q1..Q<n>)
not found in sources: <n>
```
