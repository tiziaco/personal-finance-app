---
phase: quick
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - web-app/src/hooks/use-transaction-mutations.ts
  - web-app/src/components/transactions/transactions-table.tsx
  - web-app/src/app/(app)/transactions/page.tsx
autonomous: true
requirements: []

must_haves:
  truths:
    - "Each transaction row/card shows a 3-dot menu button instead of the Edit pencil icon"
    - "Opening the 3-dot menu reveals Edit and Delete options"
    - "Clicking Edit opens the CategoryEditModal (existing behaviour preserved)"
    - "Clicking Delete calls DELETE /api/v1/transactions/batch with the single transaction ID and removes it from the list"
    - "Delete shows a success toast on completion and an error toast on failure"
  artifacts:
    - path: "web-app/src/hooks/use-transaction-mutations.ts"
      provides: "useDeleteTransaction hook"
      exports: ["useDeleteTransaction"]
    - path: "web-app/src/components/transactions/transactions-table.tsx"
      provides: "3-dot DropdownMenu in desktop Actions column and mobile TransactionCard"
  key_links:
    - from: "transactions-table.tsx DropdownMenuItem Delete"
      to: "useDeleteTransaction.mutate(id)"
      via: "onDeleteTransaction prop"
    - from: "transactions-table.tsx DropdownMenuItem Edit"
      to: "onEditTransaction(row.original)"
      via: "existing prop"
    - from: "page.tsx"
      to: "transactions-table.tsx"
      via: "onDeleteTransaction prop wired to useDeleteTransaction"
---

<objective>
Replace the single Edit pencil button in the transaction table Actions column (desktop) and TransactionCard (mobile) with a 3-dot DropdownMenu offering Edit and Delete actions. Wire Delete to the backend via a new useDeleteTransaction hook.

Purpose: Expose per-transaction delete without adding visual clutter — the 3-dot pattern is standard for row actions.
Output: Updated transactions-table.tsx with DropdownMenu, new useDeleteTransaction hook, and page.tsx wiring.
</objective>

<execution_context>
@/Users/tizianoiacovelli/.claude/get-shit-done/workflows/execute-plan.md
@/Users/tizianoiacovelli/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add useDeleteTransaction hook</name>
  <files>web-app/src/hooks/use-transaction-mutations.ts</files>
  <action>
    Append a new exported function `useDeleteTransaction` to the existing file. Do NOT modify existing hooks.

    Implementation:
    - Import `batchDeleteTransactions` from `@/lib/api/transactions` (already imported in scope — check existing imports, add if missing).
    - The hook calls `batchDeleteTransactions(token, { ids: [id] })` — a single-item batch delete matches the existing API function signature (`BatchDeleteRequest = { ids: number[] }`).
    - On success: `queryClient.invalidateQueries({ queryKey: ['transactions'] })` and `toast.success('Transaction deleted')`.
    - On error: `toast.error('Failed to delete transaction')`.
    - mutationFn signature: `async (id: number) => { ... }`.

    Pattern to follow (mirrors useDeleteAllTransactions in use-delete-all-transactions.ts for the batch-delete pattern, and useUpdateTransaction for the hook shape):

    ```ts
    export function useDeleteTransaction() {
      const { getToken } = useAuth()
      const queryClient = useQueryClient()

      return useMutation({
        mutationFn: async (id: number) => {
          const token = await getToken()
          return batchDeleteTransactions(token, { ids: [id] })
        },
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ['transactions'] })
          toast.success('Transaction deleted')
        },
        onError: () => {
          toast.error('Failed to delete transaction')
        },
      })
    }
    ```
  </action>
  <verify>npx tsc --noEmit -p /Users/tizianoiacovelli/projects/personal-finance-app/web-app/tsconfig.json 2>&1 | head -20</verify>
  <done>useDeleteTransaction is exported from use-transaction-mutations.ts with no TypeScript errors.</done>
</task>

<task type="auto">
  <name>Task 2: Replace Edit button with 3-dot DropdownMenu in table and card</name>
  <files>web-app/src/components/transactions/transactions-table.tsx</files>
  <action>
    Replace both the desktop Actions column button and the mobile TransactionCard edit button with a 3-dot DropdownMenu.

    **Step 1 — Update imports:**
    - Remove `Edit2` from lucide-react imports. Add `MoreHorizontal, Pencil, Trash2` (or whatever subset is used).
    - Add DropdownMenu imports from `@/components/ui/dropdown-menu`:
      `DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator`

    **Step 2 — Update TransactionsTableProps:**
    Add `onDeleteTransaction: (transaction: TransactionResponse) => void` alongside existing `onEditTransaction`.

    **Step 3 — Update TransactionCard component:**
    - Add `onDelete: (t: TransactionResponse) => void` to the props interface.
    - Replace the `<button onClick={() => onEdit(transaction)} ...><Edit2 /></button>` with:

    ```tsx
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className="min-h-12 min-w-12 flex items-center justify-center rounded-md hover:bg-muted"
          aria-label="Transaction actions"
        >
          <MoreHorizontal className="h-4 w-4" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => onEdit(transaction)}>
          <Pencil className="h-4 w-4 mr-2" />
          Edit
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={() => onDelete(transaction)}
          className="text-destructive focus:text-destructive"
        >
          <Trash2 className="h-4 w-4 mr-2" />
          Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
    ```

    **Step 4 — Update desktop Actions column (columnHelper.display for id: 'actions'):**
    The column cell currently renders `<Button variant="ghost" ...><Edit2 /></Button>`. Replace with equivalent DropdownMenu (same structure as card, using `row.original` instead of `transaction`, and calling `onDeleteTransaction`/`onEditTransaction` from the outer component scope via closure):

    ```tsx
    columnHelper.display({
      id: 'actions',
      header: 'Actions',
      cell: ({ row }) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="min-h-12 min-w-12"
              aria-label="Transaction actions"
            >
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => onEditTransaction(row.original)}>
              <Pencil className="h-4 w-4 mr-2" />
              Edit
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => onDeleteTransaction(row.original)}
              className="text-destructive focus:text-destructive"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    })
    ```

    **Step 5 — Update mobile card list render call:**
    Add `onDelete={onDeleteTransaction}` to `<TransactionCard ... />` in the mobile card list section.

    NOTE: The `columns` array is defined inside the component function body, so `onDeleteTransaction` is in scope via closure — no extra plumbing needed inside columns.
  </action>
  <verify>npx tsc --noEmit -p /Users/tizianoiacovelli/projects/personal-finance-app/web-app/tsconfig.json 2>&1 | head -20</verify>
  <done>TransactionsTable and TransactionCard render 3-dot menus with Edit and Delete items. No TypeScript errors.</done>
</task>

<task type="auto">
  <name>Task 3: Wire onDeleteTransaction in TransactionsPage</name>
  <files>web-app/src/app/(app)/transactions/page.tsx</files>
  <action>
    1. Import `useDeleteTransaction` from `@/hooks/use-transaction-mutations`.
    2. Instantiate the hook: `const deleteMutation = useDeleteTransaction()`.
    3. Create a handler: `function handleDeleteTransaction(transaction: TransactionResponse) { deleteMutation.mutate(transaction.id) }`.
    4. Pass it to `<TransactionsTable ... onDeleteTransaction={handleDeleteTransaction} />`.

    No other changes needed. The hook handles toast feedback internally.
  </action>
  <verify>npx tsc --noEmit -p /Users/tizianoiacovelli/projects/personal-finance-app/web-app/tsconfig.json 2>&1 | head -20</verify>
  <done>Page passes onDeleteTransaction to TransactionsTable. TypeScript reports no errors. Running the dev server and visiting /transactions shows 3-dot menus; clicking Delete removes the transaction and shows a success toast.</done>
</task>

</tasks>

<verification>
After all tasks:
- `npx tsc --noEmit` in web-app/ passes with no errors
- Desktop table shows a MoreHorizontal icon button in each Actions cell
- Mobile card shows a MoreHorizontal icon button instead of the pencil
- Clicking the 3-dot opens a menu with "Edit" and "Delete" items
- "Edit" opens CategoryEditModal (existing behaviour)
- "Delete" calls DELETE /api/v1/transactions/batch with the single ID, list refreshes, success toast appears
</verification>

<success_criteria>
- No TypeScript errors
- Both desktop table rows and mobile cards show 3-dot menus
- Edit action opens the category edit modal
- Delete action calls the backend and invalidates the transactions query
- Delete menu item is styled with text-destructive
</success_criteria>

<output>
After completion, create `.planning/quick/1-replace-transaction-action-button-with-3/1-SUMMARY.md`
</output>
