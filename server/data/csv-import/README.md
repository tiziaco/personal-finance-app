# CSV import samples

Small, made-up bank exports for checking the import by hand on a dev stack
(`/transactions` → **Import CSV**). They contain no real account data.

| File | Shape | What it exercises |
|---|---|---|
| `dkb-german-cp1252.csv` | Windows-1252, `;`, `dd.mm.yyyy`, `1.234,56`, two preamble lines, trailing `;` | Encoding fallback, preamble skip, the dropped empty column, German formats. Three monthly *Stadtwerke München* rows come out `is_recurring`. Expect 6 imported. |
| `n26-iso.csv` | UTF-8, `,`, quoted, ISO dates, dot decimals, an empty column | The N26 shape. Expect 4 imported; importing it again skips all 4 as duplicates and reuses the saved mapping. |

Keep the German file's bytes as Windows-1252 — re-saving it as UTF-8 stops it testing the fallback.
