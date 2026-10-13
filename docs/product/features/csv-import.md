# CSV import

**Status:** shipped · **Owner:** Tiziano · **Last updated:** 12 Oct 2026
**Scope:** getting transactions into the app from a bank's CSV export, in two steps — upload and
review the column mapping, then confirm and import. Legacy v1.0 shipped this; the port
rebuilds it in roadmap step 4, together with the AI categorisation.
**Data model:** pending — written with step 4.
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
   saves the rest. The user sees how many rows were imported, how many skipped as
   duplicates, and a list of rows that were rejected and why.

Date, merchant and amount must be mapped; the rest are optional.

## 3. The mapping

- **Proposed by an LLM, confirmed by the user.** The model sees the column names and up to
  three representative rows (picked to cover as many non-empty columns as possible).
- **Remembered per bank.** When the user confirms, the mapping is saved against the
  file's set of column names. The next file with the same columns skips the LLM and shows
  the saved mapping, still open to correction. A user importing from two banks has two
  profiles.
- **The upload is held for 30 minutes** between the two steps. After that, or once it has
  been confirmed, the user must upload again.

## 4. Rules and edge cases

- Only `.csv` files, UTF-8, at most **3,000 rows**.
- A file that cannot be parsed, or whose required columns cannot be mapped, is refused
  with a message saying why.
- **Bad rows are skipped, not fatal.** A row with an unreadable date, an unreadable amount
  or no merchant is left out and listed by its row number; the rest import. A date with
  no time zone is taken as UTC.
- **Duplicates are skipped**, including duplicates within the same file; see the
  fingerprint rule in [`transactions.md`](./transactions.md).
- **Importing refreshes the insights** the next time the user opens them
  ([`insights.md`](./insights.md)).
- The upload is limited to 10 a minute per user.

## 5. Not built

A live bank connection (Plaid, TrueLayer); other file formats; exporting data; choosing
the file's encoding, delimiter or date format by hand.

## 6. Open questions

- **A stricter amount format.** Amounts in a European export (`1.234,56`) depend on what
  the parser makes of them. Is a "decimal separator" choice in the mapping step needed?
- **Undoing an import.** There is no "remove everything from this file"; the user would
  select and delete rows, or delete everything.
- **Row limit.** Is 3,000 rows enough for a year of an active account, or should large
  files be split for the user?
