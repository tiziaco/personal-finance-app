# Insights

**Status:** shipped · **Owner:** Tiziano · **Last updated:** 12 Oct 2026
**Scope:** AI-written observations about the user's spending — what they are, when they are
produced, how they are shown. Legacy v1.0 shipped this; the port rebuilds it (the insights
agent and endpoint in sub-project 2, the page and dashboard callout in sub-project 3).
**Data model:** pending — written with the backend module (sub-project 2).
**Related:** [`analytics.md`](./analytics.md) · [`csv-import.md`](./csv-import.md) ·
PRD [§7](../prd-mvp.md#7-insights).

---

## 1. Who and why

Anyone with imported transactions who wants a reading of the numbers rather than the
numbers: "your subscriptions cost 84 EUR a month", "you spent three times your usual on
dining". The analytics are computed; the insights are an LLM's narrative on top of them.

## 2. What the user can do

- **Read their insights** on the insights page, sorted into five tabs: Spending Patterns,
  Recurring Charges, Savings Opportunities, Anomalies and Comparisons. Each tab says when
  the insights were generated, and an empty tab says so.
- **See the top few on the dashboard**, in a callout that links to the page.
- **Refresh them** with a Generate button. After a refresh the button is disabled for an
  hour, showing the minutes left.
- **Follow a card's call to action**, where it has one (for example, "View Recurring
  Charges").

## 3. What an insight holds

- a **type** — spending behaviour, recurring subscriptions, trend, behavioural, merchant,
  stability or anomaly;
- a **severity** — info, low, medium, high or critical;
- the **time window** it covers;
- a **summary** and, optionally, a longer **narrative**;
- the **supporting metrics** it is based on;
- a **confidence**;
- the **section** it belongs to, which decides its tab.

## 4. Rules and edge cases

- **Generated on demand and cached.** The user's insights are stored as one set, replaced on
  each regeneration. The first time the user opens them, they are generated while the page
  waits.
- **Regenerated when the data moves.** If any transaction was added after the last
  generation, opening the insights regenerates them. So importing a CSV refreshes the
  insights the next time they are opened.
- **The Generate button re-reads, it does not force.** The server regenerates only when the
  cache is stale; the button's cooldown is a browser-side timer (one hour, kept in
  local storage), not a server rule, so it does not follow the user to another browser.
- **No transactions, no insights.** A new user sees an empty state that points at the CSV
  upload.
- The endpoint is limited to 10 requests a minute per user.

## 5. Not built

- **The savings tracker.** The v1.0 plan and its milestone summary list a savings tracker
  (a checklist of savings actions) on the insights page. No such component exists in the
  v1.0 code; the page has the tabs and the Generate button only.
- Email or push alerts when something is unusual; goals; acting on an insight; sharing.

## 6. Open questions

- **Is an hour's cooldown the right rule**, and should it be the server's rather than the
  browser's, given that regeneration already depends on new data?
- **Savings tracker.** Build it, or leave "Savings Opportunities" as text only?
- **Cost.** Each regeneration is an LLM call over the user's data. With public sign-up, is a
  per-user daily cap needed?
