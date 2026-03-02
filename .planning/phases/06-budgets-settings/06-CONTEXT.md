# Phase 6: Budgets + Settings - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

The Budgets page communicates future intent without misleading users (simple "Coming Soon" placeholder visible in the sidebar). Settings gains: date format preference, a Notifications placeholder section, and a functional Delete All Transactions action — without breaking existing settings modal structure or the theme toggle.

</domain>

<decisions>
## Implementation Decisions

### Budgets page
- Simple "Coming Soon" placeholder page at `/budgets`
- Add as a nav item in the sidebar (alongside Home, Transactions, Analytics, Insights)
- Minimal design: prominent "Coming Soon" message + brief description of what budgets will offer
- No CTA (no "notify me" or other interactivity)

### Settings: General section
- Keep existing theme selector exactly as-is (already functional via `next-themes` + `useTheme()`)
- **Do NOT migrate to Tailwind `dark:` classes** — current implementation is clean and working
- Add date format preference below the theme selector
- Date format stored in **localStorage** (no backend required)
- Exposed via React Context so `formatDate()` in `lib/format.ts` reads the user's choice
- Formats offered: DD/MM/YYYY (default, current de-DE), MM/DD/YYYY (US), YYYY-MM-DD (ISO)

### Settings: Notifications section (new)
- New section added to settings dialog sidebar nav
- Contains non-functional toggle placeholders: email alerts, budget alerts, newsletter
- Clearly marked as "Coming Soon" — no real functionality
- Follows the same `SettingSection` + `Label` pattern as other sections

### Settings: Integrations section
- Remove entirely — it's a template leftover (Google Drive, Slack) with no relevance to the finance app

### Settings: Data section
- Keep section name as "Data"
- Add: "Delete All Transactions" with confirmation modal; after deletion stay on same page (empty state appears)
- Keep existing "Delete All Chats" and Memory Usage blocks — user plans to use them soon
- Update destructive button label from "Delete All Chats" to "Delete All Transactions" for the new action (keep the old chats one)

### Currency preference
- Skip entirely for this phase — no backend storage or currency converter to support it
- `formatCurrency()` remains hardcoded to EUR/de-DE

### Claude's Discretion
- Confirmation modal design and copy for Delete All Transactions
- Exact layout and spacing of the date format selector
- Toast message wording after successful transaction deletion
- How the "Coming Soon" Notifications section is visually distinguished

</decisions>

<specifics>
## Specific Ideas

- Dark theme is already working — do NOT introduce Tailwind dark: class system; keep the next-themes implementation
- Currency preference is intentionally deferred (no backend support yet)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SettingsDialog` (`components/settings/settings-dialog.tsx`): tabbed modal with sidebar nav — add "Notifications" section here, remove "Integrations"
- `GeneralSection` (`components/settings/sections/general-section.tsx`): already has working theme selector via `useTheme()` — add date format picker here
- `DataSection` (`components/settings/sections/data-section.tsx`): has existing "Delete All Chats" + Memory Usage — add Delete All Transactions alongside
- `formatDate()` in `lib/format.ts`: currently hardcoded `locale = 'de-DE'` — needs to read from user preference context
- `ThemeProvider` + `next-themes`: already wired in `layout.tsx` — theme works, do not change this
- `SettingSection` UI component: use for all new settings rows (consistent with existing pattern)
- `sonner` toast library: already in layout.tsx — use for post-deletion confirmation toast

### Established Patterns
- Settings sections are separate files in `components/settings/sections/`
- `useTheme()` pattern for reading/setting theme — model date format context on same pattern
- `formatCurrency()` / `formatDate()` in `lib/format.ts` — both accept optional locale override; context just needs to supply the right value

### Integration Points
- Sidebar nav (`components/layout/app-sidebar.tsx`): add Budgets route item
- `SettingsDialog` nav items array: remove "integrations", add "notifications"
- `lib/format.ts` `formatDate()`: wire up to date format context
- Any component calling `formatDate()` will automatically pick up the preference once context is in place

</code_context>

<deferred>
## Deferred Ideas

- Currency preference — deferred until backend user profile or localStorage-only solution is justified; no currency converter in backend yet
- Functional notification preferences — out of scope; placeholder only in this phase

</deferred>

---

*Phase: 06-budgets-settings*
*Context gathered: 2026-03-02*
