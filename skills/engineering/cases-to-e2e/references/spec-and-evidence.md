# The spec header and the evidence contract

Read this before writing a spec. The header is what QA reads to confirm your
derivation; the evidence contract is what makes a run reviewable by someone who
did not watch it. Neither is optional, and a spec written without them is the
single most common way this skill is used wrong.

## The spec header

**Open every spec with the case carried as the header doc comment**, in this
shape. The case file supplies the business content; you fill in Route and the
labelled Steps from your derivation. The spec gets read far more often than the
case file, and the header is where QA confirms your derivation:

```markdown
## <CASE-ID>: <short title>

- **Route:** /<app path> (<page state, e.g. result page, empty state>)
- **Precondition:** <data/setup that must exist before the case runs>
- **Inputs:** <files or values this case uploads/enters, or "none"; for a file, the sheet, row and column each Expected value is read from>
- **Steps:**
  1. <action, using the exact visible label>
  2. <action>
- **Expected:**
  - <observable result, written as the shipped UI actually presents it → each bullet becomes one assertion; note any wording translated from the case file>
- **Evidence:** <optional; default is video + key-moment + final screenshots, plus `<CASE-ID>-excel` when an Expected value comes from an input file>
- **Out of scope:** <optional, things this case deliberately does not verify>
```

In the TS file it becomes a leading `/** … */` block; keep the labels in the
Steps verbatim, since a reader maps them against the locators below. A grouped
spec carries one block per covered case (or one merged block listing every case
ID) plus its adaptations.

## 4. Evidence contract (every spec, no exceptions)

```ts
test.use({ video: "on" }); // spec-scoped; survives a global-config change
```

**Assertions are for the machine; the evidence is for a human who wasn't
watching the run.** Headless video renders no pointer, so a fast, cursor-less
video verifies nothing: a reviewer cannot tell where a click landed, or see a
result the test blows past in three seconds. Make every run watchable.

The contract needs four helpers in the project's shared utils fixture. Reuse
the project's equivalents if they exist; otherwise add them, with these names
or the project's own naming:

| Helper | What it must do |
| --- | --- |
| `spotlightClick(locator)` | outline the element, hold ~600ms before and after the click, leave the outline on so every click stays marked and the interaction is retraceable |
| `captureEvidence(name)` | rest the state ~1.5s, screenshot to a **stable directory outside Playwright's `outputDir`**, and attach the PNG to the report |
| `spotlightCheck(locator(s), '<CASE-ID>')` | scroll the target into view, outline it in a second colour, hold, then capture a close-up (`<CASE-ID>-close-up.png`) followed by the viewport frame with the outline still on (`<CASE-ID>.png`) |
| `showWorkbook(file, '<CASE-ID>-excel', { where, columns, note })` | render an input spreadsheet in the test's page the way a spreadsheet app shows it, highlight the rows and cells the case reads, outline them, and capture close-up then frame |

Then, per case:

- **Click through the marked-click helper**, routed through a page-object
  action (`openExportModal()`, `setPermissions()`…) so specs read as steps and
  the holds live in one place. Review-critical flows (permission setup,
  destructive confirms) get this even when a plain click would do.
- **Capture key moments as named evidence**, not just the end state: any state
  a reviewer cannot re-derive from the app later (a permission matrix
  mid-suite, a form half-filled, the row you picked) gets its own capture.
  Because every test ends on a capture, the end-state hold comes for free.
- **Show the point every case is about — scroll to it, mark it, zoom on it.**
  `expect()` leaves no trace: a value checked in a row forty rows down is
  invisible in the video and below the fold of a full-page shot, so the
  reviewer sees a page and has to take the pass on faith. Each case therefore
  ends with a spotlight check on the exact element(s) its Expected names: the
  cell, the one row, the seven column headers, the two rows an absent record
  would sit between. A locator resolving to many elements outlines them all;
  several locators go in as an array. A case that reads two screens gets one
  spotlight per screen, suffixed (`<CASE-ID>-page-2`).

  **Check whether `fullPage` even works in this app** before relying on it: in
  a shell whose main pane scrolls inside itself, `fullPage` yields one viewport
  frame of wherever the pane happens to be scrolled — which is what "the
  screenshots don't scroll" means when QA says it.
- **The value must be whole in the frame.** Wide tables scroll horizontally at
  a 1280px viewport and clip their right-hand columns; `999,999.99` shot as
  `999,999.9` reads to QA as a missing decimal — a false format defect. Give
  the spotlight helper a zoom-to-fit option and pass it whenever the point is a
  list or a right-hand column: it should zoom out the way Ctrl − does, for
  vertical *and* horizontal overflow, with an unchanged frame size and a floor
  around 40%. **Never enlarge the viewport**, because testers' screens differ.
  Outline every element the case asserts, not the first one — a `.nth(6)` cell
  is one cell of the first row, so give the page object a column locator
  instead.
- **Show the file when an Expected value comes from it.** A reviewer holding
  the evidence does not hold the upload, so a result value the file decides —
  an amount it sets, a name it carries, a row it lists or zeroes — cannot be
  checked from the result frame alone. Draw the file before the app is opened:
  `where` picks rows by header text, `columns` names the cells the value comes
  from, `note` says in one line what they decide. Decide **per Expected
  bullet**, not per case: a value some other system or the engine decides (a
  reason code, a failing row's `0.00`, a computed count) gets no file, because
  showing one claims a link that is not there. The test that uploads shows the
  whole file first (no `where`), so the video holds the input before the app
  reads it. Capture the file **before** the result, so the result frame stays
  the case's last match. Make the helper throw when `where` matches no row or
  names a missing column, so the evidence never shows a file with nothing
  marked.

  An input that is not a spreadsheet (CSV, TXT, JSON, a raw body) is attached
  as itself, named by case: `testInfo.attach('<CASE-ID>-csv', { path })` or
  `testInfo.attach('<CASE-ID>-input', { body, contentType: 'text/plain' })`.
  `e2e-run-evidence` draws it and stacks it above the result. A plain
  attachment marks no cell, so when the case reads particular rows of such a
  file, name them on the header's **Inputs** line.
- **An absence case shows its reference too.** "X is not shown" proves nothing
  alone, because the reviewer cannot tell X was ever in the input. Show the
  precondition first, where it can still be seen: the file itself for what the
  file holds, or the upload's preview for what the app read from it — upload
  the same file, stop before the confirm step so nothing is written, and
  spotlight X's row as `<CASE-ID>-reference`. Then mark the neighbours X would
  sit between on the result. Cite the source rows in the report too.
- **Read the PNGs before reporting.** Open each case's frame and close-up and
  check that the asserted value is in frame, whole and outlined. A green test
  whose evidence doesn't show its point is a test defect to fix, not a pass to
  hand over. Sampling is not enough: one green run shipped frames whose row sat
  under the sticky header. Sweep every capture for the outline colour and open
  each one the sweep flags.
- **Name captures by case ID, nothing else.** A workbook exporter finds a
  case's image by that ID in the attachment name and keeps the **last** match,
  which is why the spotlight helper attaches the close-up first and the frame
  last. A descriptive name is fine only for a key moment belonging to no single
  case (`setup`).
- **Downloads**: assert on `suggestedFilename()` and contents; for a
  spreadsheet, read it with the project's own reader (date cells arrive as
  serial numbers, not dates).

Named screenshots stay under a stable evidence directory, outside Playwright's
cleaned `outputDir`, and are also attached to the HTML report; per-test WebM
files stay under the run's results directory. When results are wanted in Excel,
use `e2e-run-evidence`: its workbook carries ID, topic, expected result,
status, reason and image, and its standalone HTML companion embeds the videos.
Don't add unreliable WebM hyperlinks to Excel.
