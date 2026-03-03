---
phase: 05-insights
plan: 03
subsystem: ui, api
tags: [insights, python, typescript, subscriptions, savings]

# Dependency graph
requires:
  - phase: 05-insights
    provides: insights-helpers.ts SECTION_CONFIG, aggregator.py subscription insights
provides:
  - "Backend emits distinct subscription_savings_opportunity insight with section='savings'"
  - "Frontend savings_opportunities tab maps to section='savings' — no filter predicate"
  - "Tab deduplication fix: Recurring Charges and Savings Opportunities show distinct insight cards"
affects: [05-insights]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Backend section field as discriminator: each tab category maps to a unique backend section value"
    - "Guard total_monthly > 0 prevents empty savings card when no recurring costs present"

key-files:
  created: []
  modified:
    - server/app/agents/insights/aggregator.py
    - web-app/src/lib/insights-helpers.ts

key-decisions:
  - "subscription_savings_opportunity uses section='savings' (not 'subscriptions') — the section field is the sole discriminator between tabs"
  - "savings_opportunities SECTION_CONFIG filter removed — section-based routing is sufficient and correct"
  - "getCTAForInsight adds case 'savings' returning Review Subscriptions link — savings insights get same CTA as subscription insights"

patterns-established:
  - "Each display tab targets a unique backend section value — no filter predicate required when sections are properly discriminated"

requirements-completed: [INSGT-03]

# Metrics
duration: 10min
completed: 2026-03-02
---

# Phase 05 Plan 03: Tab Deduplication Bug Fix Summary

**Backend emits `subscription_savings_opportunity` with `section='savings'`; frontend savings_opportunities tab updated to target `sections: ['savings']` — Recurring Charges and Savings Opportunities now show distinct insight cards.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-02T09:09:02Z
- **Completed:** 2026-03-02T09:19:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `subscription_savings_opportunity` insight to aggregator.py with `section="savings"` — guarded by `if total_monthly > 0`
- Fixed `savings_opportunities` SECTION_CONFIG in insights-helpers.ts to use `sections: ['savings']` and removed non-discriminating filter predicate
- Added `case 'savings':` CTA branch in `getCTAForInsight` returning Review Subscriptions link
- TypeScript compiles with zero errors; Next.js build passes

## Task Commits

Each task was committed atomically:

1. **Task 1: Add savings insight with section="savings" to aggregator.py** - `e42efdd` (feat)
2. **Task 2: Fix savings_opportunities SECTION_CONFIG in insights-helpers.ts** - `84d7f5f` (fix)

**Plan metadata:** committed with docs commit (see final commit)

## Files Created/Modified
- `server/app/agents/insights/aggregator.py` - Added `subscription_savings_opportunity` Insight block after `subscription_load_index`, guarded by `if total_monthly > 0`, using `section="savings"`
- `web-app/src/lib/insights-helpers.ts` - Changed `savings_opportunities` sections from `['subscriptions']` to `['savings']`, removed filter predicate, added `case 'savings':` in getCTAForInsight

## Decisions Made
- Backend section field is the sole discriminator between tabs — once `subscription_savings_opportunity` uses `section="savings"`, the frontend needs no filter predicate
- `if total_monthly > 0` guard ensures the Savings Opportunities tab shows nothing (empty state) when there are no recurring costs, rather than a misleading €0 savings card
- CTA for 'savings' section mirrors 'subscriptions' CTA — both link to `/transactions?category=Subscriptions`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Python import verification failed due to pre-existing missing `langgraph.checkpoint.postgres` module (not installed in local environment). Verified the file via AST parse instead — syntax was clean and all required identifiers confirmed present. This is an existing environment issue unrelated to this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Tab deduplication bug is closed: INSGT-03 requirement satisfied
- All 5 insight category tabs now show distinct content
- Phase 05-insights gap closure complete — all planned insights functionality is shipped
- Ready for Phase 06 or further polish

---
*Phase: 05-insights*
*Completed: 2026-03-02*
