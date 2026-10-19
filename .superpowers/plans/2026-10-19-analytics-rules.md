# Analytics rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix five rules behind what the analytics library reports: the thin-category outlier, frequent shopping as weekly recurring, two-charge yearly subscriptions, hidden subscriptions that respect the user's untick, and date bounds on hand-entered transactions. The seed is also changed so that "not recurring" is left to the rule.

**Architecture:** The cadence changes are pure functions in `transaction/domain/recurring.py`, run on every write as today. The outlier fallback and the hidden-subscription filter are pure functions in `analytics/domain/`. `recurring_source` reaches analytics on `AnalysisRow`, with a default. The date bounds are a pydantic validator on the two write schemas.

**Tech Stack:** Python 3 / FastAPI / pydantic v2 / SQLAlchemy async, pytest (unit, plus integration on a testcontainers Postgres), `make gen-contract`.

**Spec:** `.superpowers/specs/2026-10-19-analytics-rules-design.md` (read it first). Also see `.superpowers/BRIEF.md` §3 for the parallel-branch conditions.

## Global Constraints

- Do not modify `server/app/modules/insights/` (including `figures.py`), `analytics/service.py`, `analytics/domain/spending.py`, `MonthToDateResponse` or `server/tests/conftest.py`.
- A new field on `AnalysisRow` has a default; existing `AnalysisRow(...)` and `row(...)` calls stay unchanged.
- Never hand-edit `server/openapi.json` or `web-app/packages/api-client/src/generated/`. Run `make gen-contract` from the repo root and commit what it produces.
- Fixed-amount band: within **2 %** of the cluster's seed, with at least **€0.10** of slack. One constant pair, shared by weekly and yearly.
- The weekly cadence is fixed-amount only, with **4** rows. Yearly is either 2 fixed-amount rows with no other row of the merchant's same side between them, or **3** rows in the ±15 % band. Monthly and quarterly are unchanged.
- In the outlier fallback, `atm` and `savings_investments` are never candidates. A fallback candidate must also be at least `SPIKE_MIN_SHARE_OF_MONTH` (5 %) × the period's total expenses ÷ `period.weight()`.
- `analytics/domain/*` may not import `app.modules.transaction`: import-linter contract R9 forbids it, because the package root pulls in fastapi and sqlalchemy. The literal `"user"` lives in analytics as a named constant.
- Server conventions: `server/CLAUDE.md`. Run tests from `server/` with `APP_ENV=test uv run pytest <path>`. Integration tests need Docker running.

## Review Focus

1. **A weekly fixed charge with one odd row:** a gym's €9.99 rows plus a one-off €10.50 purchase at the same merchant, which falls inside the ±15 % cluster. The cluster then fails the 2 % test, and the gym is no longer weekly. This is accepted by design. Task 1 pins it so that the behaviour is a decision, not an accident.
2. **Yearly with two rows on the same day:** "no other row between" means strictly between the first and last dates of the cluster. Task 1 pins that a third, unrelated purchase strictly between the two yearly charges blocks the 2-row form.
3. **A thin category where the all-spending window also has fewer than 5 rows, or zero spread:** this is not scored at all, with no crash and no division by zero. Task 4 pins it.
4. **Twin rows:** two identical expense rows on the same day, in a thin category. Fallback scores are looked up per row object, not per value, so both are judged. Task 4 pins it.
5. **A date on the bound itself:** 1900-01-01 and 2100-12-31 are accepted on both create and update. A PATCH without `date` is still accepted. Task 5 pins both.

---

### Task 1: Weekly and yearly cadences

**Files:**
- Modify: `server/app/modules/transaction/domain/recurring.py`
- Test: `server/tests/unit/modules/transaction/domain/test_recurring.py`

**Interfaces:**
- Produces: `detect_recurring(rows: list[RecurringRow]) -> dict[uuid.UUID, bool]`. The signature is unchanged; nothing outside this file changes.

- [ ] **Step 1: Write the failing tests** (BUGS: *Frequent shopping at one merchant is detected as recurring*; TODO: *a yearly charge…*)

```python
LIDL_AMOUNTS = ["38.20", "41.50", "39.90", "44.10", "40.30", "38.80", "45.60", "42.00", "39.10", "43.70", "40.80", "46.00"]
LIDL_GAPS = [7, 6, 8, 5, 9, 7, 6, 8, 7, 6, 8]

def test_frequent_shopping_with_varying_baskets_is_not_recurring():
    # today 9 of the 12 come out True
    rows = <one row per LIDL_AMOUNTS (negated), dated START then each LIDL_GAPS day later, DETECTED>
    assert set(detect_recurring(rows).values()) == {False}

def test_a_fixed_weekly_charge_needs_four_rows():
    assert set(verdicts(series([7, 7, 7]))) == {True}
    assert set(verdicts(series([7, 7]))) == {False}

def test_a_fixed_weekly_charge_may_skip_a_week():
    assert set(verdicts(series([7, 14, 7]))) == {True}

def test_a_weekly_charge_must_hold_its_amount():
    # -10.00, -10.15, -10.00, -10.10 weekly: all within 2 % → True
    # -10.00, -10.80, -10.00, -10.40 weekly: 10.80 is 8 % off → all False
    ...

def test_a_weekly_charge_with_an_odd_purchase_in_its_cluster_is_not_weekly():
    # Review Focus 1: four weekly -9.99 rows plus one -10.50 inside their span → all False (accepted by design)

def test_two_yearly_charges_at_one_amount_are_recurring():
    assert set(verdicts(series([365], amount="-89.90"))) == {True}

def test_two_yearly_charges_that_differ_are_not_recurring():
    # -89.90 then -98.90 365 days later (10 % apart) → both False

def test_two_yearly_charges_with_other_charges_between_are_not_recurring():
    # Review Focus 2: -7.42 on START and START+372, plus -23.10 on START+100 and -15.80 on START+200 (same merchant, money out)
    # → the two -7.42 rows False
    # A money-IN row between them does not block: -7.42 twice plus +5.00 on START+100 → the -7.42 rows True

def test_small_yearly_amounts_get_ten_cents_of_slack_not_fifty():
    # -5.68 then -5.94 at 365 days (Regional Rail, 0.26 apart) → False
    # -5.68 then -5.76 at 365 days (0.08 apart) → True
```

Update `test_cadences`:
- Every weekly case (single and skipped period) gets a third gap, so the series has 4 rows: `[7, 7]` becomes `[7, 7, 7]`, and so on, keeping each case's expected value.
- `([365], False)  # yearly needs three rows` becomes `([365], True)  # yearly, two rows at one amount`.
- `([365, 366], True)` is unchanged.
- `([30], False)` is unchanged.

`test_small_amounts_get_a_euro_of_slack` (monthly) is unchanged.

- [ ] **Step 2: Run and see them fail**

Run: `APP_ENV=test uv run pytest tests/unit/modules/transaction/domain/test_recurring.py -v`
Expected: FAIL. In particular, the Lidl test reports True verdicts, and the 4-row weekly and 2-row yearly expectations fail.

- [ ] **Step 3: Implement in `transaction/domain/recurring.py`**

- Change `Cadence` to:
  `Cadence(name: str, min_days: int, max_days: int, min_rows: Optional[int], fixed_min_rows: Optional[int], fixed_alone: bool = False)`.
  - `min_rows`: the rows needed in the ±15 % cluster; `None` means never.
  - `fixed_min_rows`: the rows needed when every row is within the fixed band of the seed; `None` means never.
  - `fixed_alone`: the fixed form also needs no other row of the side strictly between the cluster's first and last dates.
- `CADENCES`:
  - weekly `(6, 8, None, 4)`
  - monthly `(26, 35, 3, None)`
  - quarterly `(84, 98, 3, None)`
  - yearly `(350, 380, 3, 2, fixed_alone=True)`
- Constants: `_FIXED_BAND = Decimal("0.02")`, `_FIXED_SLACK = Decimal("0.10")`.
- `_clusters(rows) -> list[tuple[Decimal, list[RecurringRow]]]` keeps the seed it already computes.
- `_is_series(cluster, seed, side) -> bool`: a cadence matches when the 75 % gap test passes and either `min_rows` is met, or the fixed form is met. The fixed form means `len >= fixed_min_rows`, every `abs(abs(r.amount) - seed) <= max(seed * _FIXED_BAND, _FIXED_SLACK)`, and, when `fixed_alone`, no row of `side` outside the cluster is dated strictly between the cluster's min and max dates.
- Update the docstrings. The module docstring points to D6.

- [ ] **Step 4: Run the file**

Run: `APP_ENV=test uv run pytest tests/unit/modules/transaction/domain/test_recurring.py -v`
Expected: all PASS, including `test_legacy_fixture_flags_only_the_real_series`. If the legacy fixture now flags an extra merchant, stop and report which one and why. Do not widen the assertion without the coordinator's say.

- [ ] **Step 5: Commit**

```bash
git add server/app/modules/transaction/domain/recurring.py server/tests/unit/modules/transaction/domain/test_recurring.py
git commit -m "Recurring rule: weekly needs a fixed amount and four rows; two same-amount yearly charges are a series"
```

---

### Task 2: The seed leaves "not recurring" to the rule

**Files:**
- Modify: `server/scripts/seed_transactions.py` (`load_rows`)
- Test: `server/tests/unit/scripts/test_seed_transactions.py`

**Interfaces:**
- Consumes: `TransactionImport.is_recurring: Optional[bool]`, where `None` leaves the row to the rule and is stored as `detected` by `import_many`.

- [ ] **Step 1: Write the failing test**

```python
def test_a_true_cell_is_the_users_tick_and_anything_else_is_left_to_the_rule(tmp_path):
    # CSV with three rows: is_recurring "true", "false", ""
    rows, _ = load_rows(path, TODAY)
    assert [r.is_recurring for r in rows] == [True, None, None]
```

Check `test_an_unknown_slug_becomes_miscellaneous_and_is_counted`, which asserts `rows[0].is_recurring is True`. That row's cell must be `true`; leave the test as it is if it is.

- [ ] **Step 2: Run it; expect FAIL** (`[True, False, False]`)

Run: `APP_ENV=test uv run pytest tests/unit/scripts/test_seed_transactions.py -v`

- [ ] **Step 3: Implement** by mapping `is_recurring=True if r["is_recurring"] == "true" else None`. Update the docstring of `load_rows` to say so.

- [ ] **Step 4: Run the unit file and `tests/integration/scripts/test_seed_transactions.py`; expect PASS**

- [ ] **Step 5: Commit**

```bash
git add server/scripts/seed_transactions.py server/tests/unit/scripts/test_seed_transactions.py
git commit -m "Seed: only a ticked recurring cell is the user's; the rule judges the rest"
```

---

### Task 3: `recurring_source` reaches analytics; hidden subscriptions respect an untick

**Files:**
- Modify: `server/app/modules/transaction/schemas.py` (`AnalysisRow`)
- Modify: `server/app/modules/transaction/repository.py` (`list_active_rows_for_analysis` selects `Transaction.recurring_source`)
- Modify: `server/app/modules/analytics/domain/_aggregate.py` (`Row` protocol)
- Modify: `server/app/modules/analytics/domain/recurring.py`
- Modify: `server/tests/unit/modules/analytics/rows.py`
- Test: `server/tests/unit/modules/analytics/test_recurring.py`, `server/tests/integration/modules/transaction/test_analysis_rows.py`

**Interfaces:**
- Produces:
  - `AnalysisRow.recurring_source: str = "detected"`, the last field.
  - `Row.recurring_source -> str`, a protocol property.
  - In `rows.py`, the `Row` dataclass gains `recurring_source: str = "detected"` as its last field, and `row(..., source: str = "detected")` sets it.
- Constant in `analytics/domain/recurring.py`: `USER_SOURCE = "user"`. Its comment says that this is transaction's `recurring_source` for the user's own choice (D6), and that the domain may not import `transaction` (R9).

- [ ] **Step 1: Write the failing tests** (TODO: *a merchant the user unflagged…*)

```python
def test_a_merchant_the_user_unticked_is_never_a_hidden_subscription():
    spotify = monthly(3, "2026-06", "2026-09", "-9.99", "Spotify", recurring=False)
    assert [h.merchant for h in analyse(spotify).hidden_subscriptions] == ["Spotify"]
    unticked = [spotify[0].__class__(**{**vars(spotify[0]), "recurring_source": "user"})] + spotify[1:]  # or row(..., source="user")
    assert analyse(unticked).hidden_subscriptions == ()

def test_an_untick_before_the_period_still_excludes_the_merchant():
    # one user/false Spotify row in 2026-01, three detected ones in 2026-07..09; analyse(months=3) → ()
```

In `test_returns_plain_rows_in_date_order` (integration), create the Landlord row with `recurring_source="user"` if `make_transaction` accepts it (check its signature in the transaction integration `conftest.py`; do not edit `server/tests/conftest.py`). Expect `recurring_source="user"` on that row and `"detected"` on REWE. If `make_transaction` cannot set it, update the row with the session before reading.

- [ ] **Step 2: Run them; expect FAIL**

Run: `APP_ENV=test uv run pytest tests/unit/modules/analytics/test_recurring.py tests/integration/modules/transaction/test_analysis_rows.py -v`

- [ ] **Step 3: Implement the plumbing and the filter.** In `recurring_analysis`, a merchant key is excluded from `unflagged` when it is in `ever_flagged`, or when any expense in all of `rows` has `recurring_source == USER_SOURCE and not is_recurring`. Update the docstring of `HiddenSubscription` and the module docstring.

- [ ] **Step 4: Run the analytics unit suite and the transaction integration tests; expect PASS**

Run: `APP_ENV=test uv run pytest tests/unit/modules/analytics tests/integration/modules/transaction -v`

- [ ] **Step 5: Commit**

```bash
git add server/app/modules/transaction/schemas.py server/app/modules/transaction/repository.py \
  server/app/modules/analytics/domain/_aggregate.py server/app/modules/analytics/domain/recurring.py \
  server/tests/unit/modules/analytics/rows.py server/tests/unit/modules/analytics/test_recurring.py \
  server/tests/integration/modules/transaction/test_analysis_rows.py
git commit -m "Hidden subscriptions: a merchant the user unticked is never suggested"
```

`AnalysisRow` is not in the OpenAPI spec, so no contract change is expected. If the pre-commit hook regenerates anything, include it.

---

### Task 4: Outlier fallback for a thin category

**Files:**
- Modify: `server/app/modules/analytics/domain/anomalies.py`
- Modify: `server/app/modules/analytics/schemas.py` (`OutlierResponse` only)
- Regenerate: `server/openapi.json`, `web-app/packages/api-client/src/generated/` (via `make gen-contract`)
- Test: `server/tests/unit/modules/analytics/test_anomalies.py`

**Interfaces:**
- Produces:
  - `Outlier.compared_with: Literal["category", "all"]`, a new last field with no default.
  - `OutlierResponse.compared_with: Literal["category", "all"] = Field(..., description="What the expense was compared with: its category's window, or all one-off spending when the category's window held fewer than 5")`.
  - The description of `window_mean` becomes "The mean of the window it was compared with".
- Constant: `FALLBACK_EXCLUDED = frozenset({"atm", "savings_investments"})`.

- [ ] **Step 1: Write the failing tests** (BUGS: *A large one-off purchase in a sparse category…*)

```python
def september_groceries():
    # one food_groceries row a day, 2026-09-01..30, amount f"-{10 + (i * 7) % 21}.00" (mean about €20)

ELECTRONICS = [("2026-09-03", "-19.99"), ("2026-09-10", "-34.50"), ("2026-09-17", "-12.00"), ("2026-09-24", "-49.00")]

def test_a_large_purchase_in_a_thin_category_is_compared_with_all_spending():
    # september_groceries + ELECTRONICS (media_electronics, "Saturn") + 2026-09-28 -1249.00 "Apple Store" media_electronics
    # today: no outliers
    flagged = [o for o in analyse(rows).outliers if o.merchant == "Apple Store"]
    assert len(flagged) == 1 and flagged[0].compared_with == "all"
    # window_mean is the mean of all one-off expenses in the 30 days before 2026-09-28
    assert flagged[0].window_mean == money(mean(<those amounts>))

def test_a_thin_category_purchase_under_five_percent_of_monthly_spend_is_not_flagged():
    # same groceries; one -90.00 in "media_electronics" on 2026-09-28 (z above 2.5 against all, under 5 % of the month's spend
    # only if the month's spend is above 1,800, so pad the period with enough spend, e.g. a -1500.00 recurring rent row,
    # which counts in the floor's base but is never in a window) → no outlier

@pytest.mark.parametrize("category", ["atm", "savings_investments"])
def test_moved_money_is_never_a_fallback_outlier(category):
    # groceries + one -1249.00 row in `category` → no outlier

def test_a_dense_category_is_still_compared_with_itself():
    # extend test_flags_an_expense_far_above_its_trailing_window: expected Outlier(..., "category")

def test_a_thin_window_with_too_little_spending_overall_is_not_scored():
    # Review Focus 3: BASE[:2] in shopping, two groceries rows, then -1000.00 in media_electronics → ()
    # and five identical -10.00 rows across categories, then -1000.00 thin → () (zero spread)

def test_twin_expenses_in_a_thin_category_are_both_judged():
    # Review Focus 4: groceries + two identical -1249.00 Apple Store rows on 2026-09-28 → two outliers, both "all"
```

Existing tests:
- Add the `compared_with` argument to every `Outlier(...)` literal.
- `test_fewer_than_five_prior_expenses_never_flag` stays as it is (4 rows in total), but rename it to say "in the whole window".
- Extend `_brute_force_outliers` with the fallback, the floor and the exclusion, and return `compared_with` in each tuple.
- In `test_outliers_match_a_brute_force_reference_over_two_years`, draw categories with `rng.choices(["food_groceries", "shopping", "media_electronics", "atm"], weights=[45, 45, 7, 3])[0]`, so that the fallback is exercised. Then assert that some expected tuple has `"all"`.

- [ ] **Step 2: Run the file; expect FAIL** on the laptop test, and on each literal that has no `compared_with`.

Run: `APP_ENV=test uv run pytest tests/unit/modules/analytics/test_anomalies.py -v`

- [ ] **Step 3: Implement in `anomalies.py`**

- Generalise `_outliers` into `_scores(spent: Sequence[Row], period: Period, window_days: int) -> list[_Score]`, using the same prefix sums. Define `_Score` as a frozen dataclass with `row: Row`, `n: int`, `z: Optional[float]` (None when `n < MIN_WINDOW_EXPENSES` or the spread is ≤ 0) and `window_mean: Optional[Decimal]`. There is one score per in-period row of `spent`.
- In `find_anomalies`:
  1. Score `one_off` once across all categories, keyed by `id(score.row)`.
  2. For each category group, score it. A score with `n >= MIN_WINDOW_EXPENSES` decides as today, with `"category"`.
  3. Otherwise, if the category is not in `FALLBACK_EXCLUDED` and `spend(row) >= floor`, use the all-spending score with `"all"`.
  4. The floor is `SPIKE_MIN_SHARE_OF_MONTH * total_spend(expenses(period.rows(rows))) / period.weight()`.
- The sort, the `MAX_OUTLIERS` cap and the O(n log n) cost stay.
- Update the module, `Outlier` and `find_anomalies` docstrings.

- [ ] **Step 4: Add the field to `OutlierResponse`, then run the file and the analytics schema tests; expect PASS**

Run: `APP_ENV=test uv run pytest tests/unit/modules/analytics -v`

- [ ] **Step 5: Regenerate the contract and run the contract test**

Run, from the repo root: `make gen-contract`
Then, from `server/`: `APP_ENV=test uv run pytest tests/unit/api/test_openapi_contract.py`
Expected: `openapi.json` and the generated client gain `compared_with`. The test passes.

Then, from the repo root: `make check-web`
Expected: passes. The web code does not read outliers.

- [ ] **Step 6: Commit**

```bash
git add server/app/modules/analytics/domain/anomalies.py server/app/modules/analytics/schemas.py \
  server/tests/unit/modules/analytics/test_anomalies.py server/openapi.json web-app/packages/api-client/src/generated
git commit -m "Outliers: a thin category falls back to all one-off spending, and each outlier says which"
```

---

### Task 5: Date bounds on add and edit

**Files:**
- Modify: `server/app/modules/transaction/schemas.py` (`TransactionCreate.date`, `TransactionUpdate.date`)
- Test: `server/tests/integration/modules/transaction/router/test_transactions.py`

**Interfaces:**
- Consumes: `MIN_DATE`, `MAX_DATE` from `transaction/domain/dates.py`.

- [ ] **Step 1: Write the failing tests** (TODO: *a transaction added by hand is not held to the date bounds*)

```python
# TestCreate.test_invalid_input_is_422: add {"date": "1899-12-31"} and {"date": "2101-01-01"}

@pytest.mark.parametrize("day", ["1900-01-01", "2100-12-31"])
async def test_a_date_on_the_bounds_is_201(self, authenticated_client, day): ...

# TestUpdate:
@pytest.mark.parametrize("day", ["1899-12-31", "2101-01-01"])
async def test_a_date_outside_the_bounds_is_422(self, authenticated_client, test_user, make_transaction, day): ...
async def test_a_date_on_the_bounds_is_200(...)  # "1900-01-01"
# the existing partial-edit test already covers a PATCH without a date (Review Focus 5)
```

- [ ] **Step 2: Run them; expect FAIL** (201 or 200 where 422 is expected)

Run: `APP_ENV=test uv run pytest tests/integration/modules/transaction/router/test_transactions.py -v`

- [ ] **Step 3: Implement** a date type in `schemas.py`:
  - `AnalysableDate = Annotated[dt.date, AfterValidator(_within_bounds)]`, where `_within_bounds` raises `ValueError(f"must be between {MIN_DATE} and {MAX_DATE}")`.
  - Use it for `TransactionCreate.date` and `TransactionUpdate.date`, which becomes `Optional[AnalysableDate]`.
  - The 422 then comes from FastAPI's request validation.

- [ ] **Step 4: Run the file; expect PASS.** Then run `make gen-contract` from the root. The spec is expected to be unchanged, or to change only in its descriptions; commit whatever it produces.

- [ ] **Step 5: Commit**

```bash
git add server/app/modules/transaction/schemas.py server/tests/integration/modules/transaction/router/test_transactions.py
git commit -m "Transactions: a hand-entered date must lie within the dates analytics covers"
```

No web change. The form's date comes from a calendar picker, and a 422 from it surfaces through the app's existing error toast (the planner's call, recorded in the handoff).

---

### Task 6: Docs, and the closing of the BUGS and TODO entries

**Files:**
- Modify: `docs/product/features/analytics.md` §3: the outlier bullet and the hidden-subscription bullet.
- Modify: `docs/data-model/transaction.md` D6 (see the steps below).
- Modify: `docs/BUGS.md`: remove the two bugs.
- Modify: `docs/TODO.md`: remove *a yearly charge…*, *a merchant the user unflagged…* and *a transaction added by hand is not held to the date bounds*. Add **Insights — word an outlier by what it was compared with**.

- [ ] **Step 1: Make the doc edits**

`analytics.md` §3:
- The outlier bullet describes the 5-row category window and the fallback to all one-off spending in the same window. It covers the `atm` and `savings_investments` exclusion, the 5 %-of-average-monthly-spend floor (shared with spikes) and `compared_with`.
- The hidden-subscription bullet adds: "or one the user has unticked on any charge".

`transaction.md` D6:
- Update the cadence table: weekly 6–8, 4 rows, fixed amount only; yearly 350–380, 2 at a fixed amount with nothing between them, or 3.
- Define the fixed amount as within 2 % of the seed, at least €0.10.
- Replace the "three rows, not two" paragraph with the reason for each change, dated 19 Oct 2026: Lidl, the €7.42 venue and Regional Rail.
- Add that existing flags were not re-judged because only dev data existed, so you re-seed or re-import to see the new rules.
- Change the seed sentence: "a `true` cell is `user`; any other is left to the rule."

The new TODO entry says that insights reads outliers but words every one as "above its category". It should use `compared_with` to say "above your usual spending" when the value is `"all"`. It is owned by whoever next touches `insights/`.

- [ ] **Step 2: Run both checks**

Run: `make check-server` from the repo root, then `APP_ENV=test uv run pytest` from `server/`.
Expected: both pass (the second needs Docker for the integration tests).

- [ ] **Step 3: Commit**

```bash
git add docs/
git commit -m "Docs: analytics rules — outlier fallback, weekly and yearly cadences, hidden subscriptions, date bounds"
```

The roadmap row, and the removal of the spec and plan, happen in `superpowers:finishing-a-development-branch`, once the PR URL exists (BRIEF §4).
