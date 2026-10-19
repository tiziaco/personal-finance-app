# Design System (Finsight) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the app to Finsight and restyle every screen to the `finsight-design` system (tokens, Onest, radius, charts, rail sidebar, signed amounts, category icons) without moving any layout.

**Architecture:** The design system's raw tokens land once in `@app/ui` as CSS variables, and shadcn's semantic variables are mapped onto them, so primitives and screens restyle through the cascade. Behavioural changes are small: the sidebar primitive gets a rail width and size, amounts get one sign/tone helper, and categories get a slug-to-icon map. Each is a focused file with co-located Vitest tests.

**Tech Stack:** Next.js 16, Tailwind v4 (`@theme`), shadcn on Base UI, lucide-react 1.x, recharts, next-themes, Clerk v6, Vitest + Testing Library.

**Spec:** `.superpowers/specs/2026-10-19-design-system-design.md`. Read it first; this plan argues from it.

## Global Constraints

- Source of truth for every value: `.claude/skills/finsight-design/` (`tokens/*.css`, `readme.md`, `components/core/*.jsx`). Never import its JSX or its CDN `Icon`.
- No layout changes. A screen whose layout moved is a regression.
- Sidebar width uses Tailwind's spacing scale: `w-26` / `6.5rem`. Never `w-[104px]` or a pixel style.
- Dark mode stays next-themes' `.dark` class. The design system's `[data-theme="dark"]` values are written under `.dark`.
- Package boundaries (`web-app/CLAUDE.md`): `@app/components` imports only `@app/core`, `@app/ui`, `lucide-react` (plus `next/*` as today). Base UI: `render`, not `asChild`.
- No new runtime dependency. Onest via `next/font/google`.
- Colours only through tokens. No hard-coded hex or `emerald-*` / `red-*` in components.
- One transaction's amount: `−€84.20` / `+€3,200.00`. True minus U+2212, no space, locale from `Intl`. Expense in normal text colour, income `--positive`. Totals stay unsigned.
- Copy: sentence case, no exclamation marks, no emoji.
- Tests are co-located; read the `web-app-testing` skill before touching one. Gate: `make check-web` and `make test-web` from the repo root.
- Commit messages follow the repo's style (`Design system: …`) and end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. A zero or `-0.00` amount: shows no sign and the neutral colour, never `−€0.00` or a green `+€0.00`. Pinned in Task 2.
2. A category slug the map doesn't know (added on the server later): the `Tag` fallback, never a crash or an empty tile. Pinned in Task 3.
3. A locale whose symbol trails (it-IT): the sign still leads, `−84,20 €`, and no hyphen-minus leaks through. Pinned in Task 2.
4. A user without an image, or with a one-word name: the avatar-only trigger still has an accessible name and initials. Pinned in Task 5.
5. Phone width: the rail opens as a slide-out from a trigger that's only visible below `md`, and there is no collapse on desktop. Pinned in Task 5 (test) and Task 7 (browser).

---

### Task 1: Tokens, font, type and radius

**Files:**
- Create: `web-app/packages/ui/src/styles/finsight-tokens.css`
- Modify: `web-app/packages/ui/src/styles/globals.css`
- Modify: `web-app/apps/web/src/app/layout.tsx` (Inter → Onest)
- Modify: `web-app/packages/ui/src/primitives/badge.tsx`, `web-app/packages/data-table/src/filters/filter-chip.tsx` (`rounded-md` → `rounded-full`)
- Modify: `web-app/packages/ui/src/primitives/card.tsx` (`CardTitle`), `dialog.tsx` / `alert-dialog.tsx` (titles)
- Modify: `.claude/skills/web-app-patterns/references/components.md` ("Corner radius")

**Interfaces:**
- Produces, as CSS variables (light in `:root`, dark in `.dark`): every design-system token from `tokens/colors.css`, `charts.css`, `spacing.css` (`--navy-*`, `--gold-*`, `--ink-*`, `--income-*`, `--expense-*`, `--bg-*`, `--text-*`, `--brand*`, `--logo-body`, `--logo-clasp`, `--logo-dot`, `--positive`, `--negative`, `--chart-1…6`, `--chart-other`, `--chart-income`, `--chart-expense`, `--chart-grid`, `--chart-axis`, `--chart-gap`, `--shadow-sm/md/lg`).
- Produces Tailwind utilities via `@theme inline`: `text-positive`, `text-negative`, `fill-positive`, `fill-negative`, `bg-chart-other`, and type utilities `text-display`, `text-h1`, `text-h2`, `text-h3`, `text-body`, `text-label`, `text-caption`, `text-balance` (each with its `--line-height` and `--font-weight` from `typography.css`).

- [ ] **Step 1: Copy the design system's tokens into `finsight-tokens.css`.** Keep the names and values from `tokens/colors.css`, `charts.css` and `spacing.css`. Rewrite each `[data-theme="dark"]` block as `.dark`. Leave out the sidebar and logo size tokens; Task 5 uses Tailwind units. Import it at the top of `globals.css`.

- [ ] **Step 2: Map shadcn's semantic variables onto the tokens** in `globals.css`, replacing every oklch value. Light / dark:

| shadcn var | light | dark |
|---|---|---|
| `--background` | `var(--bg-page)` | same (the token flips) |
| `--foreground`, `--card-foreground`, `--popover-foreground` | `var(--text-primary)` | same |
| `--card`, `--popover` | `var(--bg-surface)` | same |
| `--primary` / `--primary-foreground` | `var(--brand)` / `var(--text-on-brand)` | same (gold on navy ink) |
| `--secondary`, `--muted` | `var(--bg-subtle)` | same |
| `--secondary-foreground` | `var(--text-primary)` | same |
| `--muted-foreground` | `var(--text-muted)` | same |
| `--accent` / `--accent-foreground` | `var(--brand-soft)` / `var(--brand)` | same |
| `--destructive` | `var(--negative)` | same |
| `--border`, `--input` | `var(--border-default)` | same |
| `--ring` | `var(--brand-hover)` | same |
| `--sidebar` / `--sidebar-foreground` | `var(--bg-sidebar)` / `var(--text-muted)` | same |
| `--sidebar-primary` / `-foreground` | `var(--brand)` / `var(--text-on-brand)` | same |
| `--sidebar-accent` / `-foreground` | `var(--brand-soft)` / `var(--brand)` | same |
| `--sidebar-border` / `--sidebar-ring` | `var(--border-default)` / `var(--brand-hover)` | same |

Since every row reads a token that flips under `.dark`, the `.dark` block of semantic variables can go, keeping only what has no token. Delete the old chart hex values and the "dataviz-validated" comment.

- [ ] **Step 3: Pin the radius scale in `@theme inline`**, replacing the `calc(var(--radius) * …)` lines: `--radius-sm: 6px; --radius-md: 8px; --radius-lg: 12px; --radius-xl: 16px;`. Keep `2xl`–`4xl` derived. With this, existing `rounded-lg` (controls, floating lists) is 12px and `rounded-xl` (surfaces) is 16px, with no class edits. Then change `badge.tsx` and `filter-chip.tsx`'s `rounded-md` to `rounded-full`.

- [ ] **Step 4: Add the type and colour utilities** listed under Interfaces to `@theme inline`. Add `body { font-feature-settings: "tnum" 1, "lnum" 1; }` to the base layer. Use `text-h3` for `CardTitle` and `text-h2` for dialog titles.

- [ ] **Step 5: Swap the font in `layout.tsx`**: `Onest({ subsets: ["latin"], weight: ["400","500","600","700"], variable: "--font-sans" })`, replacing Inter.

- [ ] **Step 6: Rewrite "Corner radius" in `components.md`** to the spec's radius table. Floating lists use `rounded-lg` and their items `rounded-md`. Badges and chips are `rounded-full`. Note that the values come from `finsight-design`.

- [ ] **Step 7: Verify.** Run `make check-web && make test-web` from the repo root. Expected: pass. (A test asserting the badge's `rounded-md` class, if any, is updated to `rounded-full`.) Run the app (`/run-stack`), sign in (memory: `browser-sign-in-clerk-impersonate`), and screenshot `/home` in light and dark. Expected: tinted page, white (navy in dark) cards, Onest, navy/gold primary.

- [ ] **Step 8: Commit** with `Design system: the Finsight tokens, Onest and the radius scale`.

---

### Task 2: One sign and tone rule for amounts

**Files:**
- Modify: `web-app/apps/web/src/components/transactions/format.ts`, `format.test.ts`
- Modify: `web-app/apps/web/src/components/analytics/format.ts`, `format.test.ts`
- Modify: `web-app/apps/web/src/components/analytics/change.tsx` (`TONE_CLASS`, `TONE_FILL`)
- Modify (call sites): `dashboard/recent-transactions.tsx`, `transactions/transaction-card.tsx`, `transactions/use-transaction-columns.tsx`, `dashboard/summary-cards.tsx`, `dashboard/month-to-date-card.tsx`, `analytics/flow-tab.tsx`, `analytics/category-movers.tsx`, and their tests

**Interfaces:**
- Produces (in `transactions/format.ts`):
  - `formatSignedAmount(amount: string, locale?: string): string`: `"-84.20"` → `"−€84.20"`, `"3200"` → `"+€3,200.00"` (en-GB). Zero or `-0.00` → the unsigned `formatAmount` text. It formats the absolute value with `Intl` and prefixes `−`/`+`.
  - `transactionAmountClass(amount: string): string`: `"text-positive"` when the amount is above zero, `""` otherwise. Replaces `amountClass`, which is deleted.
  - `formatAmount(amount: string)` is unchanged; it's used for totals.
- Produces (in `analytics/format.ts`): `amountTone(amount: string, goodWhen: "up" | "down"): Tone`, which is `"neutral"` at zero. A net uses `"up"`; a change in spending uses `"down"`.
- `TONE_CLASS` / `TONE_FILL` in `change.tsx` become `good: "text-positive" / "fill-positive"`, `bad: "text-negative" / "fill-negative"`, neutral unchanged. These are the only tone colours in the app.

- [ ] **Step 1: Write the failing tests** in `transactions/format.test.ts`:

```ts
describe("formatSignedAmount", () => {
  it("signs with a true minus and a plus, no space", () => {
    expect(formatSignedAmount("-84.20", "en-GB")).toBe("−€84.20")
    expect(formatSignedAmount("3200", "en-GB")).toBe("+€3,200.00")
  })
  it("leads with the sign when the symbol trails", () => {
    expect(formatSignedAmount("-84.20", "it-IT")).toBe("−84,20 €")
  })
  it("never signs a zero and never emits a hyphen-minus", () => {
    expect(formatSignedAmount("0.00", "en-GB")).toBe("€0.00")
    expect(formatSignedAmount("-0.00", "en-GB")).toBe("€0.00")
    expect(formatSignedAmount("-1.00")).not.toContain("-")
  })
})
describe("transactionAmountClass", () => {
  it("greens income only", () => {
    expect(transactionAmountClass("12.00")).toBe("text-positive")
    expect(transactionAmountClass("-12.00")).toBe("")
    expect(transactionAmountClass("0.00")).toBe("")
  })
})
```

In `analytics/format.test.ts`:

```ts
it("tones a net and a spending change", () => {
  expect(amountTone("-5.00", "up")).toBe("bad")
  expect(amountTone("5.00", "up")).toBe("good")
  expect(amountTone("5.00", "down")).toBe("bad")
  expect(amountTone("0.00", "up")).toBe("neutral")
})
```

If Intl's it-IT separator in the test environment isn't U+00A0, assert with `/^−84,20\s€$/u` instead.

- [ ] **Step 2: Run them.** `cd web-app && pnpm vitest run apps/web/src/components/transactions/format.test.ts apps/web/src/components/analytics/format.test.ts`. Expected: FAIL, functions not exported.

- [ ] **Step 3: Implement** the three functions and the `TONE_CLASS` / `TONE_FILL` change as specified under Interfaces. Delete `amountClass`.

- [ ] **Step 4: Move the call sites.**
  - Transaction rows (recent transactions, transaction card, table amount cell): `formatSignedAmount` + `transactionAmountClass`.
  - Signed-by-nature figures use `formatSignedAmount` + `TONE_CLASS[amountTone(x, "up")]`: Home's Net Balance and Average Cashflow (replacing the hard-coded `text-destructive`), month-to-date "Net", Flow's net, per-month net and average (replacing `netClass`, which is deleted).
  - Category movers' `change_amount`: `formatSignedAmount` + `TONE_CLASS[amountTone(x, "down")]`.
  - Every other `formatAmount` call stays as it is.

- [ ] **Step 5: Run the web suite.** `make test-web`. Tests asserting the old text or classes (`summary-cards`, `month-to-date-card`, `flow-tab`, `transactions-table`, `month-to-date-strip`, `category-tab`) fail only on the sign, the minus or the class. Update those assertions to the new values. Expected: PASS.

- [ ] **Step 6: Commit** with `Design system: signed amounts, only income green, one tone rule`.

---

### Task 3: An icon per category

**Files:**
- Create: `web-app/apps/web/src/components/transactions/category-icon.tsx`, `category-icon.test.tsx`
- Modify: `dashboard/recent-transactions.tsx`, `transactions/transaction-card.tsx`, `transactions/use-transaction-columns.tsx` (merchant cell), `transactions/category-picker.tsx`, `analytics/category-ranking.tsx`

**Interfaces:**
- Produces:
  - `CATEGORY_ICONS: Record<string, LucideIcon>`: exactly the spec's 20-row table (`income` → `ArrowDownLeftIcon` … `miscellaneous` → `ShapesIcon`).
  - `categoryIcon(slug: string): LucideIcon`, which falls back to `TagIcon`.
  - `<CategoryTile slug={string} size?: "md" | "sm" />`: the neutral tile. `md` is `size-9` with an 18px icon; `sm` is `size-8` with a 16px icon. It uses `rounded-lg bg-muted text-muted-foreground` (`--bg-subtle` / `--text-secondary`) and is `aria-hidden`.
  - `<CategoryGlyph slug={string} />`: the bare 16px icon, used inline, `aria-hidden`.

- [ ] **Step 1: Write the failing test** `category-icon.test.tsx`:

```ts
it("maps every server category and falls back to Tag", () => {
  const slugs = ["income","salary","transportation","household_utilities","tax_fines","food_groceries","food_delivery","bars_restaurants","atm","insurances","shopping","education","family_friends","donations_charity","healthcare_drug_stores","leisure_entertainment","media_electronics","savings_investments","travel_holidays","miscellaneous"]
  for (const s of slugs) expect(CATEGORY_ICONS[s]).toBeDefined()
  expect(Object.keys(CATEGORY_ICONS)).toHaveLength(20)
  expect(categoryIcon("food_delivery")).toBe(BikeIcon)
  expect(categoryIcon("not_a_category")).toBe(TagIcon)
})
it("renders a tile for an unknown slug without throwing", () => {
  const { container } = render(<CategoryTile slug="not_a_category" />)
  expect(container.querySelector("svg")).not.toBeNull()
})
```

- [ ] **Step 2: Run it.** `pnpm vitest run apps/web/src/components/transactions/category-icon.test.tsx`. Expected: FAIL, module not found.

- [ ] **Step 3: Implement `category-icon.tsx`** per Interfaces. Check that each icon name exists in the installed lucide-react 1.x; `tsc` fails on a missing one.

- [ ] **Step 4: Place it.**
  - A `md` tile leads Home's recent-transaction rows: the merchant cell on `md+`, the list item on phones.
  - A `md` tile leads the mobile `TransactionCard`.
  - A `sm` tile leads the table's merchant cell: a `cell` renderer with `flex items-center gap-3`, keeping the merchant text truncating.
  - A `CategoryGlyph` goes before each label in the picker's options and before the name in `CategoryRanking`.
  - The category chip and every column stay where they are.

- [ ] **Step 5: Run** `make test-web`. Expected: PASS. Tests that query a row's text still pass because the tile is `aria-hidden`. Fix any that counted children.

- [ ] **Step 6: Commit** with `Design system: an icon per category on transaction rows, the picker and the ranking`.

---

### Task 4: Chart colours and the dashed expense line

**Files:**
- Modify: `web-app/apps/web/src/components/dashboard/category-slices.ts`, `category-slices.test.ts`
- Modify: `web-app/apps/web/src/components/dashboard/trend-chart.tsx`
- Modify: `web-app/packages/ui/src/primitives/chart.tsx` (grid and axis colour, only if it hard-codes them)

**Interfaces:**
- Consumes: `--chart-other`, `--chart-grid`, `--chart-axis` from Task 1.

- [ ] **Step 1: Update the failing expectation** in `category-slices.test.ts`: the `null` category slice's `fill` is `"var(--chart-other)"`; slices 1–5 stay `var(--chart-1…5)`.
- [ ] **Step 2: Run it.** `pnpm vitest run apps/web/src/components/dashboard/category-slices.test.ts`. Expected: FAIL (`--chart-6`).
- [ ] **Step 3: Implement.** Use `var(--chart-other)` for Other in `category-slices.ts`. In `trend-chart.tsx`, the expenses `<Line>` gets `strokeDasharray="6 4"`. The legend swatch for expenses shows the same dash if the legend draws lines; otherwise leave it. Grid and axis strokes use `var(--chart-grid)` / `var(--chart-axis)` wherever recharts parts set a colour. No bar hatching, no end labels, and Trends' rolling-average dash is untouched.
- [ ] **Step 4: Run** `make test-web`. Expected: PASS.
- [ ] **Step 5: Commit** with `Design system: the chart palette, Other in grey, expenses dashed beside income`.

---

### Task 5: The rail sidebar

**Files:**
- Modify: `web-app/packages/ui/src/primitives/sidebar.tsx`
- Create: `web-app/packages/components/src/layout/finsight-mark.tsx`
- Delete: `web-app/packages/components/src/layout/company-logo.tsx`
- Modify: `web-app/packages/components/src/layout/app-sidebar.tsx`, `nav-sidebar.tsx`, `user-panel.tsx`, `user-panel.test.tsx`
- Create: `web-app/packages/components/src/layout/app-sidebar.test.tsx`
- Modify: `web-app/packages/core/src/types/nav.ts` (drop the unused `items`)
- Modify: `web-app/apps/web/src/app/(dashboard)/layout.tsx`

**Interfaces:**
- Produces:
  - `SIDEBAR_WIDTH = SIDEBAR_WIDTH_MOBILE = "6.5rem"`.
  - `sidebarMenuButtonVariants` gains `size: "rail"`: `h-auto flex-col gap-1 py-2.5 px-0 justify-center text-center text-caption [&_svg]:size-5`, with the label not truncated.
  - `SidebarProvider` no longer binds the `b` shortcut. Delete `SIDEBAR_KEYBOARD_SHORTCUT` and its effect.
  - `<FinsightMark className?: string />`: the wallet mark as inline SVG (the four shapes from the design system's `Sidebar.jsx`, viewBox `6 8 56 48`), filled with `var(--logo-body)`, `var(--logo-clasp)`, `var(--logo-dot)`, so it follows the theme. `aria-label="Finsight"`, `role="img"`.
  - `AppSidebar` props: `{ items: NavItem[]; settingsSlot?: ReactNode; userSlot?: ReactNode } & ComponentProps<typeof Sidebar>`. `logoSrc` and `logoAlt` are gone.
  - `UserDetailsPanel`'s trigger renders only the avatar (`size-9 rounded-lg`) with `aria-label={user.name}`. Its menu keeps the name and email header, Account, then Log out.

- [ ] **Step 1: Write the failing tests.** New `app-sidebar.test.tsx`, which mocks `next/navigation`'s `usePathname` to `"/transactions"` and wraps in `SidebarProvider`:

```ts
it("shows every page's label and marks the current one", () => {
  renderSidebar()
  for (const t of ["Home", "Transactions", "Analytics", "Insights", "Chat"])
    expect(screen.getByRole("link", { name: t })).toBeVisible()
  expect(screen.getByRole("link", { name: "Transactions" })).toHaveAttribute("aria-current", "page")
})
it("puts Settings above the user, last in the rail", () => {
  renderSidebar({ settingsSlot: <button>Settings</button>, userSlot: <button>Ada</button> })
  const s = screen.getByRole("button", { name: "Settings" })
  const u = screen.getByRole("button", { name: "Ada" })
  expect(s.compareDocumentPosition(u) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
})
it("has the Finsight mark and no collapse trigger", () => {
  renderSidebar()
  expect(screen.getByRole("img", { name: "Finsight" })).toBeInTheDocument()
  expect(document.querySelector('[data-sidebar="trigger"]')).toBeNull()
})
```

In `user-panel.test.tsx`, add:

```ts
it("shows only the avatar until opened, named for screen readers", () => {
  renderPanel({ user: { name: "Ada", email: "ada@test.dev" } })
  expect(screen.getByRole("button", { name: "Ada" })).toBeInTheDocument()
  expect(screen.queryByText("ada@test.dev")).not.toBeInTheDocument()
})
```

The existing tests stay. `openMenu` still finds the button by `/Ada Lovelace/` through `aria-label`.

- [ ] **Step 2: Run them.** `pnpm vitest run packages/components/src/layout`. Expected: FAIL (no mark, the email visible in the trigger).

- [ ] **Step 3: Change the primitive** per Interfaces. Nothing else in `sidebar.tsx` moves. The settings dialog's inner `Sidebar` keeps `w-50`.

- [ ] **Step 4: Rebuild the components.**
  - `AppSidebar`: `<Sidebar>` in its default offcanvas mode with no `variant`. The header holds `<FinsightMark className="w-14" />`, centred. The content holds the nav. The footer holds the settings slot, then the user slot.
  - `MenuNavigator`: one `SidebarMenuButton size="rail"` per item, rendering a `Link` with the icon above `<span>{title}</span>`, plus `aria-current`. No `tooltip`, no `Collapsible` branch.
  - `UserDetailsPanel`: drop the `ChevronsUpDown` and the name/email in the trigger, and the `isMobile` side logic if unused.
  - Delete `company-logo.tsx` and `NavItem.items`.

- [ ] **Step 5: Update the layout.**
  - Remove `logoSrc`, `logoAlt` and `variant="floating"`.
  - The settings trigger becomes `<SidebarMenuButton size="rail"><SettingsIcon /><span>Settings</span></SidebarMenuButton>`.
  - `SidebarTrigger` gets `md:hidden`, so it only shows on phones.
  - Content padding widens to `px-6 py-6 md:px-8 md:py-7` (gutters only, no structural change).

- [ ] **Step 6: Run** `make check-web && make test-web`. Expected: PASS.

- [ ] **Step 7: Check in the browser** at desktop width and at 375px. Expected:
  - "Transactions" fits under its icon without truncating. If it doesn't, stop and ask the user (spec).
  - The phone trigger opens a rail-width slide-out.
  - `Ctrl+B` does nothing.
  - Settings opens the dialog; the avatar opens the menu.

- [ ] **Step 8: Commit** with `Design system: the 104px rail sidebar with the Finsight mark`.

---

### Task 6: The Finsight brand

**Files:**
- Modify: `web-app/apps/web/src/app/layout.tsx` (metadata, Clerk `appearance`)
- Create: `web-app/apps/web/src/app/icon.svg` (copy of `.claude/skills/finsight-design/assets/finsight-app-tile.svg`)
- Delete: `web-app/apps/web/public/icons/favicon.ico`, `web-app/apps/web/public/images/logo-small.png` (after a grep confirms nothing else uses them)
- Modify: `web-app/apps/web/src/app/(auth)/sign-in/[[...sign-in]]/page.tsx`, `sign-up/[[...sign-up]]/page.tsx`
- Modify: `docs/setup/clerk.md`, `web-app/apps/web/README.md`, and any other non-build file `grep -rl "Personal Finance" --exclude-dir=node_modules --exclude-dir=.next` finds, except the Clerk dashboard

**Interfaces:**
- Consumes: `FinsightMark` from Task 5 (`@app/components/layout/finsight-mark`).

- [ ] **Step 1: Read Next 16's metadata and icon conventions** in `web-app/node_modules/next/dist/docs/` (search "icon" and "metadata"). Then:
  - Set `title: "Finsight"`.
  - Set `description: "Finsight shows where your money goes, month by month, so you can decide what to change."`.
  - Drop `icons` in favour of `app/icon.svg`.
- [ ] **Step 2: Build the auth pages.** Above `<SignIn />` / `<SignUp />`, put a centred lockup: `<FinsightMark className="w-14" />` plus "Finsight" in `text-h1 font-bold tracking-tight`, inside the existing centred column. `bg-background` gives the tinted page.
- [ ] **Step 3: Theme Clerk through `ClerkProvider`'s `appearance.variables`**:
  - `colorPrimary: "var(--primary)"`
  - `colorText: "var(--foreground)"`
  - `colorBackground: "var(--card)"`
  - `colorInputBackground: "var(--card)"`
  - `colorInputText: "var(--foreground)"`
  - `fontFamily: "var(--font-sans)"`
  - `borderRadius: "0.75rem"`

  Check both themes in the browser. If this Clerk version rejects `var()` in `variables`, use `appearance.elements` with the same tokens as Tailwind classes instead. Don't add `@clerk/themes`.
- [ ] **Step 4: Rename the product in the docs** found by the grep.
- [ ] **Step 5: Verify.** Run `make check-web && make test-web`, then check in the browser. Expected: the tab reads "Finsight" with the navy tile icon, and sign-in shows the lockup and a Finsight-coloured Clerk card in light and dark.
- [ ] **Step 6: Commit** with `Design system: the app is Finsight — name, mark, tab icon, sign-in`.

---

### Task 7: Copy casing and the screen sweep

**Files:**
- Modify: `dashboard/summary-cards.tsx` ("Total spent", "Recurring costs", "Net balance", "Average cashflow"), `analytics/analytics-page.tsx` ("By category"), `packages/components/src/settings/server-status-indicator.tsx` ("Server status", "Not ready"), and their tests
- Modify: whatever the sweep below finds

- [ ] **Step 1: Fix the casing** in the files above, and in tests asserting the old strings. Run `make test-web`. Expected: PASS.
- [ ] **Step 2: Find leftover hard-coded colours.**
  ```bash
  grep -rnE "emerald-|red-[0-9]|green-[0-9]|blue-[0-9]|bg-white|text-black|#[0-9a-fA-F]{6}|oklch\(" web-app/apps/web/src web-app/packages/*/src --include=*.tsx --include=*.ts
  ```
  Expected: no hits outside `*.test.*` and `finsight-mark.tsx`. Move any hit onto a token.
- [ ] **Step 3: Sweep every screen.** Visit `/home`, `/transactions` (table, filters, the bulk bar, the add/edit, delete and import dialogs), `/analytics` (every tab), `/insights`, `/chat`, the Settings dialog, a loading state, a toast, and `/sign-in`. Do this in light and dark, at desktop width and 375px, with the seeded data. Expected:
  - No layout moved.
  - Corners follow the spec's table.
  - No stock-shadcn blue or grey remains.
  - Long merchant names still truncate beside the tile.

  Fix what's off, run `make check-web && make test-web`, then commit with `Design system: sentence case and the last screens on tokens`.

---

### Task 8: Docs close-out

**Files:**
- Modify: `docs/TODO.md` (delete **Web — legacy's theme**)
- Modify: `docs/architecture/web-app.md` (a short "Design system" section)
- Modify: `docs/ROADMAP.md` (the Design system row and wave table move to done, per its own rules)
- Delete: `.superpowers/specs/2026-10-19-design-system-design.md`, `.superpowers/plans/2026-10-19-design-system.md`

- [ ] **Step 1: Write the architecture section.** It records that `finsight-design` is the source of the tokens, and that `packages/ui/src/styles/finsight-tokens.css` is their one home in code. It states the amount rule (signed transaction amounts, income only in green, unsigned totals, `amountTone` for signed-by-nature figures). It says the category-icon map lives in `apps/web/src/components/transactions/category-icon.tsx` and needs a row whenever the server's `CATEGORIES` gains one. Add that last point beside `CATEGORIES` in `docs/data-model/transaction.md`'s "Add a category" bullet too.
- [ ] **Step 2: Delete the TODO entry, update the roadmap, and delete the spec and this plan.**
- [ ] **Step 3: Commit** with `Design system: docs — the token home, the amount rule, the icon map; spec and plan retired`.
