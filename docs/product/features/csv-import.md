# CSV import

**Status:** shipped · **Owner:** Tiziano · **Last updated:** 15 Oct 2026
**Scope:** getting transactions into the app from a bank's CSV export, in two steps — upload and
review the column mapping, then confirm and import. Legacy v1.0 shipped this; the port
rebuilds it in roadmap step 4, together with the AI categorisation.
**Data model:** [`transaction.md`](../../data-model/transaction.md).
**Related:** [`transactions.md`](./transactions.md) · [`categorisation.md`](./categorisation.md) ·
[`insights.md`](./insights.md) · PRD [§4](../prd-mvp.md#4-csv-import).

---

## 1. Who and why

Everyone: the CSV is the only way transactions get in. Banks name their columns
differently (a German export has `Buchungsdatum`, `Empfaenger`, `Betrag`), so the app
cannot assume a format. It asks an LLM to propose which column is which, and the user
confirms before anything is saved.

## 2. What the user can do

1. **Upload** a `.csv` file from the transactions page, by dragging it in or browsing.
2. **Review the mapping.** The app shows each of the file's columns with the field it
   proposes (date, merchant, amount, description, original category, recurring, or
   ignore), a few sample rows, and how empty each column is. The user can change any
   assignment.
3. **Confirm.** The app reads the whole file, categorises every row, skips duplicates, and
   saves the rest. The user sees four counts — rows imported, skipped as duplicates, filed
   under Miscellaneous because no category could be found, and rejected — and a list of the
   rejected rows and why. The dialog can be closed while the import carries on; a notice
   reports the result when it finishes, and reopens it.

Date, merchant and amount must be mapped; the rest are optional.

## 3. The mapping

- **Proposed by an LLM, confirmed by the user.** The model sees the column names and up to
  three representative rows (picked to cover as many non-empty columns as possible).
- **Remembered per bank.** When the user confirms, the mapping is saved against the
  file's set of column names. The next file with the same columns skips the LLM and shows
  the saved mapping, still open to correction. Profiles are keyed by the (case-folded) column set, not
  by bank: two banks with different headers have two profiles, and two with identical headers
  share one.
- **The upload is held for 30 minutes** between the two steps. After that, or once it has
  been confirmed, the user must upload again.

## 4. Rules and edge cases

- Only `.csv` files, at most 5 MB and **3,000 rows**, in UTF-8 or Windows-1252.
- **The format is inferred, then shown.** The delimiter (`,` `;` tab or `|`), and each
  column's date format and decimal style (`1.234,56` or `1,234.56`), are worked out from the
  file and displayed in the review. Lines above the header, such as an account summary some
  banks print first, are skipped.
- A file that cannot be read is refused with a message saying why: not a `.csv` name
  (`not_csv`), over 5 MB (`too_large`), empty (`empty`), no header row (`no_header`),
  a column with no name (`unnamed_column`) or two with the same name (`duplicate_column`), no
  data rows (`no_rows`), more than 3,000 (`too_many_rows`), or a file the CSV reader cannot
  parse, an unbalanced quote for one (`malformed`). A mapping that leaves date, merchant or
  amount unmapped is refused at confirm, not at upload, so the review can still be corrected.
- **Bad rows are skipped, not fatal.** A row with an unreadable date, a date outside 1900–2100
  (analytics reads nothing outside it), an unreadable amount, no merchant, or more cells than
  the header (trailing empty cells are fine) is left out and listed by its row number — the
  file's own line number, so lines above the header shift it;
  the rest import. A date with a time keeps its date as written.
- **Duplicates are skipped, counted.** A row is a duplicate of one the user already holds, by
  the fingerprint rule in [`transactions.md`](./transactions.md). Counting matters: two
  identical rows in one file are two transactions, and importing the same file again adds
  nothing.
- **A mapped recurring column is the user's assertion.** Its value is kept and the
  recurring rule never changes it; a blank cell lets the rule decide
  ([`transaction.md`](../../data-model/transaction.md) D6).
- **Importing refreshes the insights** the next time the user opens them
  ([`insights.md`](./insights.md)).
- Upload and confirm are limited to 10 uploads and 10 confirms a minute **per user**.
- A new upload replaces the held one; a confirm for the replaced upload is refused as expired.

## 5. Not built

A live bank connection (Plaid, TrueLayer); other file formats; exporting data; choosing
the file's encoding, delimiter or date format by hand; selecting several files at once.

## 6. Open questions

- **Undoing an import.** There is no "remove everything from this file"; the user would
  select and delete rows, or delete everything.
- **Row limit.** Is 3,000 rows enough for a year of an active account, or should large
  files be split for the user?
