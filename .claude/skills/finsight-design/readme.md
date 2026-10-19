# Finsight Design System

**Finsight** is a personal finance web app: balances, transactions, budgets and goals in a dashboard with a 96px icon sidebar. This system covers the logo, colour, type and the first dashboard components. Light and dark modes are first-class.

Sources: no external brand material. The system was designed in an earlier Claude Design project (mounted locally as `Finsight/`: logo rounds, palette, type comparison) and consolidated here. No Figma or GitHub links.

## Content fundamentals
- Plain, calm, second person ("Set a monthly budget to track it."). No jargon, no exclamation marks, no emoji.
- Sentence case everywhere; labels short (Overview, Activity, Budgets).
- Amounts always signed and spaced: `+ $ 3,200.00`, `− $ 84.20` (true minus sign). Insights state a comparison: "12% less than last month".

## Visual foundations
- **Colour:** navy `#1C2447` brand, gold `#F2B53E` accent (clasp, highlights, primary in dark mode), navy-tinted neutrals. Status: income green, expense red, warning gold, info blue. Dark mode via `data-theme="dark"`: near-white logo body, gold primary.
- **Type:** Onest only (400/500/600/700) for text and numbers; tabular + lining figures on by default. Mono (JetBrains Mono) only for tokens/specs, not UI.
- **Shape:** soft. Radii 6/8/12/16; buttons and inputs 12, cards 16. Pills for badges.
- **Elevation:** 1px border plus a very light shadow on cards; larger shadows only for overlays.
- **Backgrounds:** flat page tint, white surfaces. No gradients, textures or imagery.
- **States:** hover shifts brand to navy-500 (gold-lighter in dark); disabled 50% opacity; focus is a 3px ring (`--focus-ring`).
- **Layout:** fixed 96px sidebar, fluid content, 24–32px gutters, 16px card gaps.

## Charts
- **Categorical:** `--chart-1…6` + `--chart-other` (navy, gold, teal, coral, sky, plum). Order alternates dark/light; dark mode swaps navy for a lighter periwinkle.
- **Many categories:** show the top 6 by value, group the rest into one grey "Other · N" slice (drill down on click). Never exceed 7 colours. Percentages and amounts live in the legend, not as slice labels.
- **Income vs expenses:** `--chart-income` solid, `--chart-expense` dashed, with direct end labels so colour is never the only cue.
- Segment gaps use `--chart-gap` (the surface colour); gridlines `--chart-grid`.

## Logo
Wallet mark: body, folded flap at 45% opacity, gold clasp with a dot. Always freestanding in the app (no tile). Use 50–100px wide in the sidebar. The navy app tile is only for stores, home screens and favicons.
- `assets/finsight-mark.svg` light mode · `assets/finsight-mark-dark.svg` dark mode · `assets/finsight-app-tile.svg`
- Wordmark: "Finsight", Onest 700, tracking −0.02em, navy.

## Iconography
Lucide (stroke 2, 20px) loaded from CDN as a mask via `Icon`. **Substitution:** no icon set was supplied; swap if you have one. No emoji, no unicode icons.

## Fonts
Onest and JetBrains Mono load from Google Fonts (`tokens/fonts.css`). No font files supplied; self-host them if needed.

## Index
- `styles.css` → `tokens/` (fonts, colors, typography, spacing)
- `assets/` logo SVGs · `guidelines/` foundation cards
- `components/core/` Icon, Button, Badge, Input, Card, StatCard, TransactionRow, Sidebar (+ `core.card.html`)
- `ui_kits/dashboard/` overview screen with light/dark toggle (starting point)
- Only one product surface (web dashboard) exists; no slides or marketing site were provided.
- `thumbnail.html` project tile · `SKILL.md` agent-skill entry

## Intentional additions
Icon (wrapper for the Lucide set) and Sidebar, StatCard, TransactionRow (finance-specific).
