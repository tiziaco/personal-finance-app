---
phase: 01-foundation
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - web-app/src/types/transaction.ts
  - web-app/src/types/analytics.ts
  - web-app/src/types/insights.ts
autonomous: true
requirements:
  - FOUND-01

must_haves:
  truths:
    - "TypeScript types exist for every backend API response shape"
    - "CategoryEnum covers all 20 category values from the Python model"
    - "amount is typed as string (not number) throughout all transaction types"
    - "TransactionFilters covers all query params accepted by GET /api/v1/transactions"
    - "AnalyticsResponse is typed with Record<string, unknown> for the data field (narrowing deferred to Phase 2/4)"
    - "InsightsResponse, Insight, InsightType, and SeverityLevel are fully typed"
  artifacts:
    - path: "web-app/src/types/transaction.ts"
      provides: "TransactionResponse, TransactionListResponse, TransactionFilters, CategoryEnum, CATEGORY_OPTIONS, BatchUpdateRequest/Response, BatchDeleteRequest/Response"
      exports:
        - CategoryEnum
        - TransactionResponse
        - TransactionListResponse
        - TransactionFilters
        - CATEGORY_OPTIONS
        - BatchUpdateItem
        - BatchUpdateRequest
        - BatchUpdateResponse
        - BatchDeleteRequest
        - BatchDeleteResponse
    - path: "web-app/src/types/analytics.ts"
      provides: "DashboardResponse, AnalyticsResponse, AnalyticsFilters"
      exports:
        - AnalyticsResponse
        - DashboardResponse
        - AnalyticsFilters
    - path: "web-app/src/types/insights.ts"
      provides: "InsightsResponse, Insight, InsightType, SeverityLevel"
      exports:
        - InsightType
        - SeverityLevel
        - Insight
        - InsightsResponse
  key_links:
    - from: "web-app/src/types/transaction.ts"
      to: "web-app/src/lib/api/transactions.ts"
      via: "type imports in Plan 03"
      pattern: "import.*from.*@/types/transaction"
    - from: "web-app/src/types/analytics.ts"
      to: "web-app/src/lib/api/analytics.ts"
      via: "type imports in Plan 03"
      pattern: "import.*from.*@/types/analytics"
    - from: "web-app/src/types/insights.ts"
      to: "web-app/src/lib/api/insights.ts"
      via: "type imports in Plan 03"
      pattern: "import.*from.*@/types/insights"
---

<objective>
Create all TypeScript interfaces that exactly mirror the Pydantic backend schemas. These types are the foundation consumed by every plan in this phase and every page in subsequent phases.

Purpose: Establish a single source of truth for every API response shape. Once these interfaces exist, all downstream code (API functions, hooks, components) has a typed contract to implement against — no TypeScript errors, no surprises at runtime.

Output: Three type files covering transactions, analytics, and insights.
</objective>

<execution_context>
@/Users/tizianoiacovelli/.claude/get-shit-done/workflows/execute-plan.md
@/Users/tizianoiacovelli/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/STATE.md

The backend schemas are finalized — these types must mirror them exactly. Key constraints:
- `amount` on TransactionResponse MUST be `string` (Python Decimal serializes as JSON string — typing as number silently loses precision on financial values)
- `date`, `created_at`, `updated_at`, `generated_at` are ISO 8601 strings, never Date objects
- CategoryEnum must include all 20 categories from server/app/models/transaction.py
- AnalyticsResponse.data is `Record<string, unknown>` — the backend schema is `Dict[str, Any]`; narrowing happens in Phase 2/4
- CATEGORY_OPTIONS is a const array derived from CategoryEnum — used by useCategories hook (Plan 05) without an API call
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create transaction types</name>
  <files>web-app/src/types/transaction.ts</files>
  <action>
Create `web-app/src/types/transaction.ts` with the following exports (in this order):

1. **CategoryEnum** — TypeScript union type with exactly these 20 string literals (from server/app/models/transaction.py CategoryEnum):
   'Income' | 'Transportation' | 'Salary' | 'Household & Utilities' | 'Tax & Fines' | 'Miscellaneous' | 'Food & Groceries' | 'Food Delivery' | 'ATM' | 'Insurances' | 'Shopping' | 'Bars & Restaurants' | 'Education' | 'Family & Friends' | 'Donations & Charity' | 'Healthcare & Drug Stores' | 'Leisure & Entertainment' | 'Media & Electronics' | 'Savings & Investments' | 'Travel & Holidays'

2. **CATEGORY_OPTIONS** — a `const` array of type `CategoryEnum[]` listing all 20 values (used by useCategories hook — there is NO /categories API endpoint, categories are static)

3. **TransactionResponse** — interface matching server/app/schemas/transaction.py TransactionResponse:
   ```
   id: number
   user_id: string
   date: string           // ISO 8601 — do NOT use Date type
   merchant: string
   amount: string         // CRITICAL: Decimal serializes as string in JSON — must NOT be number
   description: string | null
   original_category: string | null
   category: CategoryEnum
   confidence_score: number
   is_recurring: boolean
   created_at: string
   updated_at: string
   ```

4. **TransactionListResponse** — interface:
   ```
   items: TransactionResponse[]
   total: number
   offset: number
   limit: number
   ```

5. **TransactionFilters** — interface for query parameters accepted by GET /api/v1/transactions:
   ```
   date_from?: string
   date_to?: string
   category?: CategoryEnum
   merchant?: string
   amount_min?: string
   amount_max?: string
   is_recurring?: boolean
   sort_by?: 'date' | 'amount' | 'merchant'
   sort_order?: 'asc' | 'desc'
   offset?: number
   limit?: number
   ```

6. **BatchUpdateItem** — interface: `{ id: number; category?: CategoryEnum }`

7. **BatchUpdateRequest** — interface: `{ items: BatchUpdateItem[] }` (max 100 per request — add JSDoc comment)

8. **BatchUpdateResponse** — interface: `{ updated: number }`

9. **BatchDeleteRequest** — interface: `{ ids: number[] }` (max 100 per request — add JSDoc comment)

10. **BatchDeleteResponse** — interface: `{ deleted: number }`

No default exports. All named exports. No runtime code except CATEGORY_OPTIONS array.
  </action>
  <verify>
    <automated>cd /Users/tizianoiacovelli/projects/personal-finance-app/web-app && npx tsc --noEmit --skipLibCheck 2>&1 | head -20</automated>
  </verify>
  <done>
    - `web-app/src/types/transaction.ts` exists with all 10 exports
    - `CATEGORY_OPTIONS` array has exactly 20 entries
    - `amount` field is typed as `string` (not number)
    - `npx tsc --noEmit --skipLibCheck` passes with no errors from this file
  </done>
</task>

<task type="auto">
  <name>Task 2: Create analytics and insights types</name>
  <files>web-app/src/types/analytics.ts, web-app/src/types/insights.ts</files>
  <action>
**File 1: `web-app/src/types/analytics.ts`**

Create with the following exports (mirroring server/app/schemas/analytics.py):

1. **AnalyticsResponse** — interface:
   ```
   data: Record<string, unknown>   // backend types as Dict[str, Any]; narrowed in Phase 2/4
   generated_at: string            // ISO 8601
   ```

2. **DashboardResponse** — interface:
   ```
   spending: Record<string, unknown>
   categories: Record<string, unknown>
   recurring: Record<string, unknown>
   trends: Record<string, unknown>
   generated_at: string
   ```

3. **AnalyticsFilters** — interface for analytics query parameters:
   ```
   date_from?: string   // YYYY-MM-DD format
   date_to?: string     // YYYY-MM-DD format
   ```

---

**File 2: `web-app/src/types/insights.ts`**

Create with the following exports (mirroring server/app/schemas/insights.py):

1. **InsightType** — union type:
   `'spending_behavior' | 'recurring_subscriptions' | 'trend' | 'behavioral' | 'merchant' | 'stability' | 'anomaly'`

2. **SeverityLevel** — union type:
   `'info' | 'low' | 'medium' | 'high' | 'critical'`

3. **Insight** — interface:
   ```
   insight_id: string
   type: InsightType
   severity: SeverityLevel
   time_window: string
   summary: string
   narrative_analysis: string | null
   supporting_metrics: Record<string, unknown>
   confidence: number
   section: string
   ```

4. **InsightsResponse** — interface:
   ```
   insights: Insight[]
   generated_at: string   // ISO 8601
   ```

All named exports. No runtime code.
  </action>
  <verify>
    <automated>cd /Users/tizianoiacovelli/projects/personal-finance-app/web-app && npx tsc --noEmit --skipLibCheck 2>&1 | head -20</automated>
  </verify>
  <done>
    - `web-app/src/types/analytics.ts` exists with AnalyticsResponse, DashboardResponse, AnalyticsFilters
    - `web-app/src/types/insights.ts` exists with InsightType, SeverityLevel, Insight, InsightsResponse
    - `npx tsc --noEmit --skipLibCheck` passes with no errors from these files
  </done>
</task>

</tasks>

<verification>
After both tasks complete:
1. Run `cd /Users/tizianoiacovelli/projects/personal-finance-app/web-app && npx tsc --noEmit --skipLibCheck` — must produce zero errors
2. Verify `web-app/src/types/transaction.ts` exports exactly: CategoryEnum, CATEGORY_OPTIONS, TransactionResponse, TransactionListResponse, TransactionFilters, BatchUpdateItem, BatchUpdateRequest, BatchUpdateResponse, BatchDeleteRequest, BatchDeleteResponse
3. Verify `web-app/src/types/analytics.ts` exports: AnalyticsResponse, DashboardResponse, AnalyticsFilters
4. Verify `web-app/src/types/insights.ts` exports: InsightType, SeverityLevel, Insight, InsightsResponse
5. Verify `amount` in TransactionResponse is `string` (grep check)
</verification>

<success_criteria>
- Three type files exist in web-app/src/types/
- All exported names match the list in must_haves.artifacts exactly
- TypeScript compiler reports zero errors
- No `Date` object types used (all dates are strings)
- `amount` is `string` not `number`
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation/01-foundation-01-SUMMARY.md` with:
- What was created (list all files and their key exports)
- Any deviations from the plan (type shape mismatches discovered during implementation)
- Confirmation that `amount: string` constraint was applied
- TypeScript compilation status
</output>
