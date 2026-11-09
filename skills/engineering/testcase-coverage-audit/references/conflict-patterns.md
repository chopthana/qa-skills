# Conflict patterns, with the split that fixes each one

Every pattern here is a case that reads fine and cannot be executed. The fix is
always the same shape: one row, one verdict.

---

## 1. Boundary pair in one row

The commonest one, and the reason this skill exists.

**Before**

> **Steps** — 6. กรอก ID (HRIS) = 20 หลัก แล้ว Click "สร้าง"
> 7. เปิด modal ใหม่ กรอก ID (HRIS) = 21 หลัก แล้ว Click "สร้าง"
> **Expected** — 1. กรณี 20 หลัก: บันทึกได้ 2. กรณี 21 หลัก: ไม่บันทึก · แสดงข้อความแจ้งว่าให้กรอกไม่เกิน 20 หลัก

Two data sets, opposite verdicts, one Pass/Fail cell.

**After — two cases**

| | |
| --- | --- |
| **A** | กรอก 20 หลัก → ช่องรับครบ · บันทึกสำเร็จ · ตารางแสดงครบ 20 หลัก |
| **B** | กรอก 20 หลักแล้วพิมพ์หลักที่ 21 → หลักที่ 21 ไม่ถูกรับ · ค่ายังเป็น 20 หลักเดิม |

Note on B: the message the original expected (`ให้กรอกไม่เกิน 20 หลัก`) is
unreachable when the input caps at 20 — the case asserted an error that can never
appear. That is a **finding**, not a rewrite: keep the spec's intent, flag the
row, ask whether the cap is meant to be silent.

**Rule** — the last accepted value and the first rejected one never share a row.

---

## 2. Gate and payload in one row

**Before**

> **Steps** — 5. ไม่เลือกรูปแบบกะ → 6. Click "สร้าง" → 7. เปิด dropdown
> **Expected** — 1. ไม่บันทึก · banner 2. ขอบแดง "โปรดเลือกรูปแบบกะ" 3. dropdown มี 24 ตัวเลือก 4. เลือกได้ค่าเดียว มีช่องค้นหา และปุ่ม ✕

Lines 1–2 are a submit result; 3–4 are the control's content. A tester who finds
23 options cannot mark the required-validation half as passed.

**After** — one case for *required*, one for the *dropdown's contents*, one for
*search + clear*.

---

## 3. "ช่องรับเฉพาะ X" and "บันทึกไม่ได้เมื่อมี Y"

**Before**

> **Expected** — 1. ช่อง ID (HRIS) รับเฉพาะตัวเลข 2. ไม่สามารถบันทึกได้เมื่อมีตัวอักษร · แสดงข้อความแจ้งใต้ช่อง

Mutually exclusive. If line 1 holds, line 2's state is unreachable; if line 2
holds, line 1 is false. Check which gate the code actually has — an input filter
or a submit validation — and split into:

- typing letters → never enter the field (the filter)
- pasting mixed text → only the digits remain (the filter's other door)
- the submit error → **only if the code has one**; otherwise it is an open question

---

## 4. Trim: blocked and saved in one row

**Before**

> **Expected** — 1. แสดง "รหัสกะซ้ำ" 2. การเทียบตัดช่องว่างก่อนเปรียบเทียบ 3. หากบันทึกผ่าน ค่าที่จัดเก็บต้องถูกตัดช่องว่างแล้ว

Line 1 says it did not save. Line 3 describes what happens when it does. The
`หาก` is the tell.

**After** — `" ช6 "` against an existing `ช6` → duplicate, no save. And a
separate case: `" ช9-9 "` with nothing to clash with → saves, stored trimmed,
and re-entering `ช9-9` now reports a duplicate.

---

## 5. Open state and submit state in one row

**Before**

> **Expected** — 1. แสดง radio 3 ค่า 2. ไม่มีค่าเริ่มต้น 3. ไม่บันทึก · banner 4. ขอบแดง

1–2 are observed on open; 3–4 after submit. Both are worth testing and they
belong to different moments.

**After** — "ตัวเลือกที่แสดงเมื่อเปิด modal" and "บังคับเลือก — ไม่เลือกแล้วกดสร้าง".

---

## 6. Step ↔ expected drift

**Before**

> **Steps** — 4. สร้างรหัสกะใหม่ที่เลือกสี **ชมพู**
> **Expected** — 3. รองรับกรณีเลือกสี **ขาว** (badge ขอบ/พื้นขาวยังอ่านข้อความได้)

The white badge is a real risk (white on a white table) and it has no steps. Give
it its own case with its own data.

---

## 7. Cross-case disagreement

Two cases, same state, different results:

> **A** — dropdown ไม่มีตัวเลือกให้เลือก (ว่าง)
> **B** — ไม่มีตัวเลือก และแสดงข้อความ "ไม่พบ"

Merge into the one the screen actually does, and if the second half of A ("ไม่
สามารถกด 'สร้าง' สำเร็จได้") is a separate behavior, it becomes its own case.

---

## 8. Appearance and dismissal in one row

**Before**

> **Expected** — 1. แสดง dialog "…" + ปุ่ม "ตกลง" 2. กดตกลงแล้วกลับไปที่ฟอร์ม ค่าที่กรอกยังอยู่ 3. ตัวเลือก 07.00-23.00 หายจาก dropdown

Showing the dialog and what OK does are different behaviors — and across the two
error paths they differ from each other (one returns to the form, one closes it),
which is exactly the thing a merged row hides.

**After** — a case per dialog for *appears with this exact text*, and a case per
dialog for *OK does this*.

---

## 9. Duplicate coverage

A later `[Cancel]` block re-testing what three earlier cases cover. Keep the
specific cases, drop the summary one, and say in the reply which id disappeared
and which ids now carry it. Coverage never shrinks silently.

---

## 10. A rule written as an expected result

> **Expected** — 3. การตรวจสอบซ้ำของ ID (HRIS) ครอบคลุมทุก Partition

Nothing on screen says this. Either the case gets steps that demonstrate it
(create under one scope, then the same value under another) or the sentence moves to `หมายเหตุ`
as the rule being relied on.

---

## 11. Unreachable "ทุกช่อง"

> **Expected** — 2. ทุกช่องบังคับขอบแดงและมีข้อความใต้ช่อง

Check the messages constant. If two required fields have no message defined, and
a third is `disable` at that moment, "ทุกช่อง" is three different findings
wearing one sentence: the fields with messages, the fields with none (open
question), and the disabled one (its own case, after its gate is satisfied).
