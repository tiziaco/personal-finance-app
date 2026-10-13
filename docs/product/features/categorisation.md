# Categorisation

**Status:** shipped · **Owner:** Tiziano · **Last updated:** 12 Oct 2026
**Scope:** how each transaction gets a category, and how the user overrules it. Legacy v1.0
shipped this; the port rebuilds it (correcting a category in roadmap step 2,
Transactions; the labelling agent in step 4, CSV import).
**Data model:** pending — written with steps 2 and 4.
**Related:** [`csv-import.md`](./csv-import.md) · [`transactions.md`](./transactions.md) ·
PRD [§5](../prd-mvp.md#5-categorisation).

---

## 1. Who and why

Everyone who imports a file. Nobody categorises thousands of rows by hand, and the
analytics are only as good as the categories, so the app labels every imported row. The
labelling is imperfect, so correcting it must be quick.

## 2. What the user can do

- **Get categories automatically** when a CSV is confirmed. Nothing to do.
- **Change one transaction's category** from the edit dialog or the row's menu.
- **Change many at once**: select rows and pick a category.
- **Choose a category** when adding a transaction by hand.

## 3. The categories

A fixed list of twenty. The user cannot add, rename or remove categories.

Income · Salary · Transportation · Household & Utilities · Tax & Fines · Food & Groceries ·
Food Delivery · Bars & Restaurants · ATM · Insurances · Shopping · Education · Family &
Friends · Donations & Charity · Healthcare & Drug Stores · Leisure & Entertainment ·
Media & Electronics · Savings & Investments · Travel & Holidays · Miscellaneous

## 4. Rules and edge cases

- **How it works, in product terms.** The labeller recognises well-known merchants, asks an
  LLM to categorise the rest in batches, and checks the answers against the list. A
  merchant the LLM does not answer for is filed under Miscellaneous with a confidence of
  0.3.
- **Every transaction carries a confidence**, 0 to 1. Anything the user entered or edited
  by hand is 1. The transactions table shows it as a percentage, in a warning colour below
  70%.
- **The user's corrections are not learned.** The labeller was built to take a user's
  category preferences, but v1.0 never passes any; the same merchant is categorised afresh
  in every import.
- **Prompts are versioned** (v1 and v2 exist; v2 is used), so a change in wording can be
  compared.

## 5. Not built

Custom categories; subcategories; rules such as "always file this merchant under X";
learning from corrections; splitting one transaction across categories.

## 6. Open questions

- **Remember corrections?** When the user recategorises a merchant, should the next import
  follow? The hook exists in the labeller; the product decision does not.
- **Flag low confidence?** The v1.0 research proposed a "review suggested" badge below 0.85
  confidence; what shipped is a coloured percentage with a 70% cut-off. Is that enough
  to prompt a review?
- **Taxonomy.** Twenty categories were chosen for one user in Berlin ("Food Delivery",
  "Tax & Fines"). Do they fit everyone?
