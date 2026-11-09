# Template format — the two-sheet test-case workbook

**The team's own template file is the canonical source, not this doc.** Find it
(it sits beside their sprint workbooks), open it, and follow it.
`build_workbook.py` reproduces the layout described below; if the layout here
and a live template disagree, follow the template and adjust the generator.

> **Worked example** — everything below is one team's template, written out so
> the generator has something concrete to reproduce: two sheets, a Thai header
> row on row 4, and a lookup sheet feeding two dropdowns. Another team's
> template will differ in sheet names, column order and language; read theirs
> before generating.

## Workbook

Two visible sheets, in this order: **`list`** then **`TestResult`**.

### Sheet `list` — dropdown sources

| | A | B | C |
| --- | --- | --- | --- |
| 1 | `Passed` | `Unit Test` | `High` |
| 2 | `Passed with condition` | `Integration Test` | `Medium` |
| 3 | `Not pass` | `System Test` | `Low` |
| 4 | `Waiting to test` | `System Integration Test` | |
| 5 | | `UAT` | |

> Note: the template `list!A1` reads `Passed`, but some sprint workbooks read
> `Pass`. Either is acceptable; `build_workbook.py` writes `Passed`.

### Sheet `TestResult` — one row per case

Row 1–3: green banner rows (`FF007635`), mostly blank.
Row 2, col F: `โปรแกรม:` (col G holds the program name).
Row 4: the header row.

| Col | Header | Notes |
| --- | ------ | ----- |
| A | ลำดับ | formula `=IF(B5="","",ROW()-4)` |
| B | ประเภทการทดสอบ | dropdown → named range `test` |
| C | TC ID | stable id |
| D | หัวข้อ | case title |
| E | กรณีทดสอบและขั้นตอนการทดสอบ | steps, `1. …\n2. …` |
| F | ผลการทดสอบที่คาดหวัง | expected, `1. …\n2. …` |
| G | สถานะ | `Waiting to test` etc. |
| H | Tester | left blank for QA |
| I | Test date | left blank for QA |
| J | หมายเหตุ | `กรณีปกติราบรื่น` or a flag |
| K | ระดับความสำคัญ | dropdown → `$D$1:$D$3` |
| L | Remark for Pass with Condition | left blank |

Data rows start at **row 5**.

## Named range & data validation

Two validations, exactly as in the template:

1. `list` validation over `B<first>:B<last>`, source **named range `test`**
   (`TestResult!$B$1:$B$5` — yes, it points at the TestResult banner cells,
   not the `list` sheet; that is the template's own quirk, reproduce it).
2. `list` validation over `K4` and `K<first>:K1048576`, source `$D$1:$D$3`
   — note the template itself has **no C/D cells filled**; `$D$1:$D$3` is an
   empty range in the shipped file, and a different workbook relies on the
   same address. `build_workbook.py` keeps the same formula string so the
   file matches; the priority values are also written literally, so Excel's
   stale range does not matter for reading.

## Column widths

`A 11, B 21, C 13, D 73, E 87.855, F 13, G 17.57, H 16.43, I 22.57, J 42.855, K 18.285, L 37.14`

## Freeze / filter

`freeze_panes = E5` in the template. `build_workbook.py` also sets an
autofilter over `A1:K<last>` (present in the shipped template as
`_xlnm._FilterDatabase`).

## Styles

- Header row 4: `Tahoma 11`, fill `FFFF66`, all thin borders, centered.
- Data rows: sequence col A bold Tahoma 11 centered; B/G/H/I/K/L Tahoma 11;
  C bold Calibri 11 centered; D/E/F Calibri 10 wrapped, fill `F9FAFB`;
  J Segoe UI 10 wrapped, fill `F9FAFB`.

## `cases.json` schema

```jsonc
{
  "program": "ตั้งค่ารหัสกะการทำงาน",   // optional -> G2
  "type": "System Test",                 // default test type for every case
  "cases": [
    {
      "tc_id": "PROMO-CODE-SETTING-001", // required, unique
      "topic": "ตรวจสอบการเปิด modal",          // required
      "steps": ["เข้าสู่ระบบ", "..."],          // array or newline string
      "expected": ["แสดง ..."],                 // array or newline string
      "note": "กรณีปกติราบรื่น",                 // optional -> J
      "priority": "Medium",                     // High|Medium|Low -> K
      "status": "Waiting to test",              // optional -> G
      "type": "System Test",                    // optional per-case override
      "tester": null, "test_date": null, "remark": null
    }
  ]
}
```

Arrays are numbered automatically (`1. `, `2. `, …). Pass a plain string when
the source already contains its own numbering.

## TC ID conventions

Read an existing workbook before coining anything: the ID family already in use
is the convention, and a new prefix that does not match it costs QA a
translation step on every conversation about a case. Keep a per-feature
counter; never reuse an id.

**Always propose a prefix and ask the user to confirm it before generating**,
and offer alternatives rather than deciding alone.

> **Worked example** — one team uses `<AREA>-<FEATURE>-NNN`, zero-padded:
> for a promo-code settings screen that gives `PROMO-CODE-SETTING-001`
> (area `PROMO`, feature `CODE-SETTING`), with `PROMO-SETTING-` and
> `CATALOG-PROMO-CODE-` as the alternatives to offer.

## Workbook file name

Discovered, not assumed: list the folder the team keeps their workbooks in and
copy the pattern off the neighbours. Ask the user to confirm the ticket key and
the card name (both come from the ticket title) before writing the file.

> **Worked example** —
> `Test Case - <TRACKER> - {ticket_no} - {card_name}.xlsx`, e.g.
> `Test Case - QAP - 1041 - [Catalog][Promo] ตั้งค่ารหัสโปรโมชัน — Add Promo Code.xlsx`.

