# Insights

**Status:** shipped · **Owner:** Tiziano · **Last updated:** 16 Oct 2026
**Scope:** AI-written observations about the user's money — what they are, when they are
written, how they are shown. Legacy v1.0 shipped a version of this; the port rebuilt it in
roadmap step 6 (the agent, the routes, the `/insights` page and the home callout).
**Data model:** [`../../data-model/insight.md`](../../data-model/insight.md).
**Related:** [`analytics.md`](./analytics.md) · [`csv-import.md`](./csv-import.md) ·
PRD [§7](../prd-mvp.md#7-insights).

---

## 1. Who and why

Anyone with transactions who wants a reading of the numbers rather than the numbers: "your
subscriptions cost €84 a month", "you spent three times your usual on dining". The dashboard
and the analytics page show figures; insights are a short written reading of them — what
stands out, why it matters, and sometimes one thing to do about it.

The user's routine shapes the rules: they open the app once a week or once a month, upload
that period's CSV (sometimes add a transaction by hand), and look at how the period went.
Insights must be fresh after that with no thought from them: upload, open Insights, read.

Legacy filled seven fixed templates with figures and asked the model for two sentences under
each, so every user saw the same seven cards. Here **the model chooses and writes the
insights** from the analytics figures, in one call, keeping the same kinds of observation.

## 2. What the user can do

- **Read their insights on `/insights`**, the sidebar entry before Chat. The page has an **All** tab, then **Spending, Recurring, Savings, Anomalies** and
  **Comparisons**, each with its count. All lists every card by severity, high to info; ties
  keep the model's order. A tab with no cards says so in one line.
- **Regenerate.** The header shows when the set was generated ("Generated 16 Oct 2026, 14:32")
  beside a **Regenerate** button, which reads "Generating…" and is disabled while it runs.
- **See the top three on the home page**, in a callout between the charts and Recent
  transactions: severity, section and summary of each, the generated time, and **View all**.
  When the set is stale the cards are dimmed, with a note and a **Refresh insights** link to
  `/insights`; with no set yet, an invitation to open Insights.
- **Read the month so far.** Besides the insights about the last finished month, one or two
  cards may be about the month in progress, tagged "October so far" — on the page and in the
  callout.
- **Follow a card's link**, where it has one, to the transactions behind it.

## 3. What an insight holds

- a **section** — spending, recurring, savings, anomalies or comparisons; it decides the tab;
- a **severity** — info, low, medium, high or critical;
- a **period** — the finished month against the user's usual, or the month so far;
- a **summary** — one sentence, the card's title;
- a **narrative** — one to three sentences: what it means, and one concrete step where there
  is one;
- optionally a **key figure** — an amount, a percentage or a count with a few words ("€184
  / month", "+69% vs August"), formatted by the app in the browser's locale like every other
  amount;
- optionally a **link** — the recurring charges list, a category, or a merchant. Category and
  merchant links open `/transactions` filtered to it over the card's period — the finished
  month, or the month so far. A link to a
  category that does not exist, or to a merchant not in the figures the model was given, is
  dropped; the card stays.

Amounts in the summary and narrative are written by the model in one fixed form: `€` before
the number, whole euros with a comma for thousands (`€1,240`), cents only under €10
(`€4.99`), no sign — "spent", "received".

The set as a whole carries when it was generated and which month it is about. Legacy's type,
time window, supporting metrics and confidence are gone: the section carries the grouping,
the period is the set's, and a model's self-rated confidence told the user nothing.

## 4. Rules and edge cases

- **One set per user, replaced whole** on each generation. There is no history.
- **What the insights are about.** The last finished month with data — the dashboard's month
  — against "your usual", up to the six finished months with data before it (fewer for a new
  user, none for a user with one month). When the current month has data, the model also gets
  the month so far against the same days of the previous month, and may write one or two
  cards about it; they compare like with like and their severity stops at medium. A user
  whose only data is the month in progress gets insights about it, told through which day
  it runs, and never reads its lower total as a fall in spending.
- **Stale** when a transaction was added, edited, recategorised, re-flagged or deleted after
  the set was generated, or when a new calendar month has begun since.
- **Opening `/insights` with no set, or a stale one, generates** while the page waits
  (expected 10–30 s), showing the previous cards, if any, under a loading state. Opening it
  when the set is fresh costs nothing, however often.
- **Regenerate always generates**, stale or not: the model may give a different reading of
  the same figures.
- **The home callout never generates.** It only reads; the home page never waits on the
  model.
- **A failed generation keeps the previous set** on screen, with an error by the button.
  With no previous set, the page shows the error and a retry. Nothing partial is stored.
- **Zero insights is a valid answer.** A sparse month may have nothing worth saying; the set
  is stored and shows "Nothing stands out this month", so it is not regenerated on every visit.
- **No transactions, no insights.** The page shows an empty state pointing at the CSV
  upload, with no model call; the callout is not shown.
- **"Delete all transactions" in Settings deletes the set**, and so does account erasure:
  the set quotes merchants and amounts from the rows.
- **The model sees aggregates only**, never transaction rows: totals, categories, top and
  recurring merchants, behaviour, outliers and spikes. Merchant names are allowed — they make
  a card specific. Every figure in a card must come from those aggregates; the model
  narrates, it never computes.
- `POST /insights/generate` and `GET /insights` each carry a rate limit of 10 a minute per
  address, a guard against runaway clicks rather than a product rule.

## 5. Not built

- **The savings tracker.** The v1.0 plan listed a checklist of savings actions on the
  insights page; it was never built there either. Savings stay text.
- **A per-user cap on generation.** Each generation is a paid model call; only the rate
  limit guards it. Needed before public sign-up — [`TODO.md`](../../TODO.md).
- **History** of past sets; email or push **alerts**; goals; acting on an insight; sharing.
- The chat assistant does not read stored insights.
