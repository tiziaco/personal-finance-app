# Design system: the app becomes Finsight

**Roadmap step:** Design system (`feat/design-system`), before 7 Chat finance tools.
**Decided with the user:** 19 Oct 2026, in a brainstorm with mockups of the sidebar, the
amount format and the category icons.

## Intent

The app has run on the template's stock shadcn theme. A design system was made in Claude
Design and is now in the repo as the `finsight-design` skill
(`.claude/skills/finsight-design/`). This step renames the app to **Finsight** and restyles
every screen to that system, so every page, and every page built after it (step 7's chat UI
first), starts from one set of tokens and rules instead of the template's defaults.

It is a restyle, not a redesign. Each screen keeps its layout, its content and its
behaviour. What changes is the brand, the colour, the type, the shape, the sidebar's form,
how amounts read, and one addition: an icon per category.

## Source of truth

`.claude/skills/finsight-design/` is the reference. Read it before building:

- `readme.md`: the rules (content voice, colour, type, shape, elevation, states, charts,
  logo, iconography).
- `tokens/*.css`: every value. `colors.css` and `charts.css` hold light (`:root`) and dark
  (`[data-theme="dark"]`).
- `components/core/*.jsx`: reference renderings of Button, Badge, Input, Card, StatCard,
  TransactionRow, Sidebar and Icon.
- `ui_kits/dashboard/index.html`: a full screen in both themes.
- `assets/`: the logo mark (light and dark) and the app tile.

The reference components use inline styles and a CDN icon loader. They show what to match.
They are not code to import: the app keeps its shadcn / Base UI primitives in `@app/ui` and
restyles them.

## Goals

1. **The app is Finsight.** It has the wordmark and the wallet logo. The browser tab title
   is "Finsight", the favicon is made from the navy app tile, and the metadata description
   is rewritten in the design system's voice. Docs that name the product "Personal Finance"
   (`docs/setup/clerk.md`, `web-app/apps/web/README.md`, and any others a search turns up)
   follow the new name.
2. **Tokens.** The design system's colours (both themes), type scale, spacing, radii and
   shadows drive the shadcn semantic variables in `packages/ui/src/styles/globals.css`. Every
   primitive and screen picks them up from there.
3. **Font.** Onest (400/500/600/700) replaces Inter. Tabular and lining figures are on by
   default, as `typography.css` sets them.
4. **Sidebar:** the design system's icon rail (details below).
5. **Corner radius:** the design system's scale (details below).
6. **Charts:** the design system's palette and rules (details below).
7. **Amounts** in transaction lists read the way the user picked (details below).
8. **Category icons:** one per category, on the design system's neutral tile (details
   below).
9. **Every screen restyled:** Home, Transactions (table, mobile cards, filters, dialogs,
   import), Analytics, Insights, Chat, the Settings dialog, loading skeletons, toasts, and
   the sign-in and sign-up pages.

## Non-goals

- No layout changes. Home keeps its current composition; it is **not** rearranged into the
  design system mockup's greeting, three stat cards and activity-beside-budgets.
- No new pages. The mockup's Budgets and Goals do not exist in this app and are not added.
- Page names stay **Home, Transactions, Analytics, Insights, Chat**, not the mockup's
  Overview / Activity.
- No change to what any screen shows, and no server change. The category list stays on the
  server; icons are presentation only.
- The app name inside Clerk's hosted screens and emails is set in the Clerk dashboard by the
  user, not in code.

## Anti-goals (would be a failure even if it technically works)

- A second component library: importing the design system's JSX components, or inline-style
  copies of them, alongside the shadcn primitives.
- A sidebar width in raw pixels (`w-[104px]`, `style={{ width: 104 }}`). The user asked for
  Tailwind's spacing scale.
- Expense amounts in a transaction list shown in red. They stay in the normal text colour;
  only income is green (see **Amounts**).
- A screen whose layout moved. Any visible layout change is a regression for this step.
- Colours hard-coded in components. They go through tokens, so dark mode stays correct.

## Decisions

### Sidebar (user's decision: mockup "A")

- A fixed rail **`w-26` (6.5rem = 104px)**, on the design system's `Sidebar.jsx` model.
  The logo mark sits on top. Below it are the five pages, each a button with its **icon
  above a 12px label** (`--text-caption`). The active page gets the `--brand-soft`
  background and `--brand` colour; inactive pages are `--text-muted`.
- At the bottom, in this order: **Settings** (a rail button, icon over the label
  "Settings", opening the existing Settings dialog), then **the user's avatar alone** at
  the very bottom. The avatar is 36px, rounded 12px, initials on `--brand` or the Clerk
  image. It opens the existing menu, with the user's name and email at the top of the
  menu, then Account, then Log out. The trigger needs an accessible name (the user's name),
  since its text is gone.
- **Built on the existing shadcn sidebar primitive** (`packages/ui/src/primitives/sidebar.tsx`),
  with two changes to it:
  1. `SIDEBAR_WIDTH` becomes the rail width (`6.5rem`). The provider sets it as an inline
     style, so a class can't override it. The settings dialog's inner sidebar sets its own
     `w-50` and is unaffected, but check it.
  2. `sidebarMenuButtonVariants` gains a `rail` size: column layout, icon above label,
     auto height, 12px label. The existing sizes stay.
- **On a computer there is no collapse.** No `SidebarTrigger`, no `Ctrl+B`, no icon-only
  state. The `icon` width and the collapsed-state branches in the app's sidebar components
  (logo, user panel) go.
- **On a phone** the primitive's slide-out sheet stays, so the sidebar keeps its default
  (offcanvas) mode rather than `collapsible="none"`. A menu button opens it, shown on
  phones only. The sheet holds **the same rail**, so there is no phone variant of the
  buttons, logo or avatar. `SIDEBAR_WIDTH_MOBILE` becomes the rail width too (my call,
  after the builder check).
- **Wordmark:** the rail shows only the mark, as the design system's `Sidebar.jsx` does.
  The "Finsight" wordmark appears with the mark on the sign-in and sign-up pages, and
  nowhere a layout would have to move to fit it (my call, after the builder check).
- Labels replace tooltips, so the nav buttons drop the `tooltip` prop.
- "Transactions" must fit under its icon at `w-26` without truncation. If it doesn't, stop
  and ask the user; don't widen the rail or rename the page unilaterally.
- Mockup: `.superpowers/brainstorm/*/content/sidebar.html`, option A. That directory is
  not committed; the description above is the spec.

### Corner radius (user's decision: the design system's scale)

It replaces the scale in the `web-app-patterns` skill's `references/components.md`
("Corner radius"), and that section is rewritten to it in this step:

| Element | Radius |
|---|---|
| A control: button (every size), input, textarea, select trigger, sidebar menu button | 12px (`--radius-lg`) |
| A surface: card, dialog, alert dialog, the table frame, the bulk-action bar | 16px (`--radius-xl`) |
| A badge or a filter chip | pill (`--radius-pill`) |
| A floating list (popover, select and dropdown content, hover card) and its items | builder's call, on the 6/8/12/16 scale, keeping "an item is one step smaller than its list" |
| Round by nature: avatar, switch, status dot | `rounded-full` (the sidebar avatar is 12px, per the design system) |

### Charts (user's decision: the design system's colours, red included)

- Categories use `--chart-1…6` (navy, gold, teal, coral, sky, plum; periwinkle replaces navy
  in dark), and "Other" uses `--chart-other` (grey). Today "Other" uses `--chart-6`. The
  server sends its top five plus Other, so slots 1–5 plus `--chart-other` cover it.
- Income is `--chart-income` (green) and expenses `--chart-expense` (red), **everywhere the
  app uses them today**. That includes the spending-only charts (average per day,
  seasonality, trends, change in expenses). The user saw that this makes Analytics read red
  and chose it anyway.
- Where income and expenses are drawn as **two lines** in one chart, the expense line is
  dashed, per the design system, so colour is never the only cue. Bars stay solid; there is
  no hatching. A line that is dashed today for another reason, such as Trends' rolling
  average, stays as it is. The readme's direct end labels are **not** added, since they
  would change chart layouts; legends stay. (My call, after the builder check.)
- Grid and axis use `--chart-grid` / `--chart-axis`. Segment gaps use `--chart-gap`.
- The current palette's comment ("dataviz-validated") goes with it.

### Amounts (user's decision: option "A")

- **One transaction's amount** carries a sign, with a true minus (U+2212) and no space:
  `−€84.20`, `+€3,200.00`. The rest follows the user's locale through `Intl`: symbol
  position, separators, and Italian's `3200,00 €`. Note that `Intl` emits a hyphen-minus,
  so format the absolute value and prefix the sign.
- **Colour:** expenses in the normal text colour, income in `--positive` (green). This
  replaces `amountClass`'s red/emerald in `components/transactions/format.ts`.
- Applies to every list of transactions: the transactions table, the mobile transaction
  card, Home's recent transactions, and anywhere else one transaction's amount is shown.
- **Totals stay unsigned** (my call, stated to the user): a figure summing many
  transactions under a label that already says the direction, like "Spent this month", a
  category total, or a merchant total.
- **Figures signed by nature** (my call, after the builder check): Home's Net Balance
  and Average Cashflow, Analytics Flow's net and per-month net, month-to-date "Net", and
  the category movers' change amount. They use the same sign format (true minus, `+` when
  positive). Their colour follows the design system's good/bad rule (`StatCard`'s
  `trend`): `--positive` when favourable, `--negative` when unfavourable, neutral at zero.
  For a net, negative is unfavourable. For a change in spending, an increase is
  unfavourable.
- **One helper decides sign and colour for every amount**, so Home and Analytics can't
  drift apart. Today Analytics borrows `amountClass` (via `netClass` in
  `analytics/flow-tab.tsx`) while Home hard-codes `text-destructive`
  (`dashboard/summary-cards.tsx`); both move onto the helper.
- The design system's own spaced format (`− € 84.20`) was shown and not chosen.

### Category icons (user's decision: in this step, the proposed set)

A slug → Lucide icon map in the web app (not the server, not `@app/core`). Unknown slugs
fall back to `Tag`. The icon sits on the design system's neutral tile: 36px, rounded 12px,
`--bg-subtle` background, `--text-secondary` icon at 18px, as in `TransactionRow.jsx`.

| Slug | Icon | Slug | Icon |
|---|---|---|---|
| `income` | ArrowDownLeft | `shopping` | ShoppingBag |
| `salary` | Banknote | `education` | GraduationCap |
| `transportation` | Car | `family_friends` | Users |
| `household_utilities` | House | `donations_charity` | HeartHandshake |
| `tax_fines` | Landmark | `healthcare_drug_stores` | Pill |
| `food_groceries` | ShoppingCart | `leisure_entertainment` | Ticket |
| `food_delivery` | Bike | `media_electronics` | Smartphone |
| `bars_restaurants` | Utensils | `savings_investments` | PiggyBank |
| `atm` | Coins | `travel_holidays` | Plane |
| `insurances` | ShieldCheck | `miscellaneous` | Shapes |

Where it shows (my call, stated to the user, not objected to):
- every transaction row: the table, the mobile card, Home's recent transactions
- the category picker's options
- the Analytics category ranking

Not in charts or legends, where colour already identifies the category.

Placement and size (my call, after the builder check):
- **In a row** (table, mobile card, recent transactions), the tile leads the row, before
  the merchant, as in `TransactionRow.jsx`. In the table that's the start of the Merchant
  cell. The category chip stays where it is.
- **In the dense table** the tile may be 32px (16px icon) rather than 36px, to keep row
  height close to today's. Rows growing by the tile's height is accepted: the icon is an
  addition the user approved, not a layout regression.
- **In the category picker and the ranking**, the icon sits inline before the label at
  16px, without a tile.

### My calls (stated to the user, not objected to)

- **Page background:** the tinted `--bg-page` with white `--bg-surface` cards, a 1px border
  and `--shadow-sm`. Content gutters widen toward the design system's 24–32px, inside the
  existing layout.
- **Theme switching** stays as it is: next-themes with the `.dark` class and the
  Light / Dark / System setting. The design system's `[data-theme="dark"]` values are
  written under `.dark`. Dark mode makes gold the primary colour, as the design system says.
- **Copy:** labels move to sentence case, as the readme asks ("Total Spent" becomes
  "Total spent", "Net Balance" becomes "Net balance"). Casing only; no rewording. Tests
  asserting the old casing follow. (After the builder check.)
- **Icons** stay `lucide-react`, the same Lucide set the design system names, without its
  CDN loader.
- **Clerk's sign-in and sign-up components** take the Finsight colours, font, radius and
  logo, in both themes, so they don't look like another product.

## Constraints

- **Package boundaries** (`web-app/CLAUDE.md`): tokens and primitive changes in `@app/ui`;
  the sidebar, logo and user panel in `@app/components`, which may import only `@app/core`,
  `@app/ui` and `lucide-react`; category icons and amount formatting in `apps/web`. Base UI
  patterns (`render`, not `asChild`).
- Follow the `web-app-patterns` and `web-app-testing` skills. Tests are co-located; some
  existing ones assert things that change on purpose (the user panel's button name, amount
  text and colour classes) and are updated, not deleted.
- The pre-push hook (ESLint, `tsc`, Prettier, Vitest) is the only gate for `web-app/`.
- No new runtime dependency without saying why. Onest comes through `next/font/google`.
  Clerk theming beyond `appearance.variables` (for example `@clerk/themes`) counts as a
  new dependency.
- Next.js 16: check `node_modules/next/dist/docs/` for the metadata and icon file
  conventions before relying on memory.

## Docs that move in the PR that completes this step

- `docs/TODO.md` **Web — legacy's theme** is deleted. This step is that decision.
- `web-app-patterns` `references/components.md` "Corner radius" is rewritten to the table
  above.
- `docs/ROADMAP.md`: the Design system row moves to done, per the roadmap's own rules.
- Lasting facts go into `docs/`: that the design system lives in the `finsight-design`
  skill and is the source for tokens, the amount format rule, and the category-icon map's
  home. Where they go is the builder's call (e.g. `docs/architecture/web-app.md`).
- This spec and its plan are deleted.

## Left to the builder

- How the design system's raw tokens map onto shadcn's semantic variables
  (`--primary`, `--muted`, `--sidebar-*`, …), as long as the screens match the design
  system in both themes and there is one place to change a colour.
- How the logo is delivered (inline SVG reading the `--logo-*` variables, or the two SVG
  files switched by theme), its exact size within the design system's 50–100px, and the
  favicon pipeline (Next's `icon` file convention or a generated `.ico`).
- Hover, focus and disabled states, following the readme's "States".
- Floating-list radii (see the table).
- How to disable the sidebar shortcut and hide the trigger on desktop.
- Where in `apps/web` the category-icon map lives, and the shape of the tile component.
- Whether JetBrains Mono replaces the current mono font. The design system uses mono only
  for specs, not UI.

## Done looks like

- Every screen, in light and dark, at desktop and phone width, matches the design system's
  look with an unchanged layout. Checked in the running app with the seeded data.
- The tab says Finsight with the tile icon. The sidebar is the 104px rail with Settings
  then the avatar at the bottom, and the slide-out works on a phone.
- Transaction amounts read `−€84.20` / `+€3,200.00` (locale-aware). Every transaction row,
  the picker and the ranking show category icons.
- `make check-web` and `make test-web` pass.
