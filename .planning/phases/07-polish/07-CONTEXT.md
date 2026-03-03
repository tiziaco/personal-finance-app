# Phase 7: Polish - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning
**Source:** User input

<domain>
## Phase Boundary

Ensure the app looks and works correctly on every device and in both light and dark mode, with consistent design tokens, toast feedback, and skeleton loading states throughout.

</domain>

<decisions>
## Implementation Decisions

### Dark Mode
- Dark mode is managed via **next-themes** (`ThemeProvider` / `useTheme` / `class` strategy), NOT via Tailwind `dark:` utility classes directly driven by the user's OS preference
- Components should respect the theme class applied by next-themes to the `<html>` element; Tailwind `dark:` variants are still used for styling, but the toggle mechanism is next-themes

### Claude's Discretion
- Color token consolidation approach (CSS variables vs Tailwind config)
- Skeleton loading library/component choice
- Toast library/component choice (likely already in use — check existing code)
- Mobile sidebar implementation details (sheet/drawer pattern)
- Breakpoint strategy for responsive chart/table layouts

</decisions>

<specifics>
## Specific Ideas

- Design tokens: Teal `#208E95` (primary), Warm Gray `#5E5240` (secondary), Cream `#FCFCF9` (background), Charcoal `#1F2121` (dark)
- Mobile target: 375px viewport; 48px minimum tap targets
- Transaction table → card-list on mobile
- Charts: full-width on mobile, 2-column grid on desktop

</specifics>

<deferred>
## Deferred Ideas

None identified.

</deferred>

---

*Phase: 07-polish*
*Context gathered: 2026-03-03*
