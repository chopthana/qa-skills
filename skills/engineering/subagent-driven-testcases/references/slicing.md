# Cutting slices

A slice is one author's whole job. Cut badly, and the run produces duplicate
cases, an item nobody wrote, or an author that runs out of room halfway.

## Size

**8–20 cases per slice.** Under 8, the dispatch and review cost more than the
author saves you. Over 20, the author's own context fills with the cases it has
already written and the last ones thin out — which is the failure this whole
skill exists to avoid, reproduced one level down.

You are sizing in *cases*, not items: one `FR-` item with a length rule is three
or four cases; one `W-` item is part of a case. Estimate per item as you cut,
and when a slice lands over 20, split it before dispatching, not after.

## The cut, in order of preference

1. **By screen section, as the screen is actually laid out** — search
   conditions, then results table, then the create form, then the confirmation
   dialog. A tester works a screen this way, and an author briefed this way
   writes steps that hang together.
2. **By field, when one field carries many rules** — a code field with
   required + length + charset + uniqueness is a slice on its own.
3. **By state table** — all the states of one screen, one slice.
4. **By flow** — create, edit, delete as separate slices, because their steps
   diverge from the first click.

Cross-cutting slices, dispatched **last** so the shared behavior is already
settled:

- **happy path end-to-end** — one slice, a handful of cases, the whole feature
  used the way it is meant to be used.
- **wording sweep** — the `W-` items that no behavioral slice claimed: one case
  per screen state asserting every string in that state, quoted. Not one case
  per label.

## Disjointness

One item, one owning slice. When two slices both want an item:

- the item belongs to the slice that *tests* it, not the one that *passes
  through* it. A login string belongs to the wording sweep, not to every slice
  whose steps start at sign-in.
- if both genuinely test it, the cut is wrong — the boundary is in the middle of
  one behavior. Move it.

Write the claim list per slice into the ledger and check the union against the
inventory **before** the first dispatch. Items left over go into a slice or onto
a `Parked:` line with a reason. There is no third option.

## Worked example

> A promo-code feature: 1 list screen, 1 create form, 1 confirmation dialog.
> Inventory: 38 items (AC 6, FR 11, ST 5, FL 3, W 12, NF 1).

| slice | what | items claimed | est. cases | model |
| --- | --- | --- | --- | --- |
| S1 | List screen: search + filters | `AC-1` `AC-5` `FR-search-trim` `ST-no-results` `FL-search` | 11 | mid |
| S2 | List screen: results table + pagination | `AC-6` `ST-empty` `ST-partial` `NF-page-limit` | 9 | cheap |
| S3 | Create form: code field rules | `AC-2` `FR-code-required` `FR-code-length` `FR-code-charset` `FR-code-unique` | 14 | mid |
| S4 | Create form: remaining fields + defaults | `AC-3` `FR-name-required` `FR-branch-default` `FR-status-default` `FR-date-range` | 12 | cheap |
| S5 | Confirmation dialog + cancel mid-way | `AC-4` `FL-create` `FL-cancel` `ST-saving-error` | 10 | mid |
| S6 | Wording sweep (last) | every remaining `W-` item | 6 | cheap |
| S7 | Happy path end-to-end (last) | `FL-create` ∩ `AC-1..4` (assertions only) | 3 | mid |

38 items, 7 slices, ~65 cases, 2 fan-out rounds (S1–S5 together, then S6–S7).

Note S7 claims no item of its own: an end-to-end slice asserts items other
slices own, so give it an explicit **no-claim** marker in the ledger rather than
double-claiming — otherwise the merge's duplicate scan will be right to
complain.

> The table is invented. A real run's slices follow that feature's own screen
> sections.

## Re-cutting mid-run

An author reporting `NEEDS_CONTEXT` because its slice turned out to span two
behaviors is a cutting error, not an author error. Record a ruling, cut the
remainder into a new slice, dispatch it, and leave the first author's written
cases in place — they are reviewed on their own file like any other slice.
