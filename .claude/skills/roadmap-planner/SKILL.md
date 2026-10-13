---
name: roadmap-planner
description: Shaping docs/ROADMAP.md with the user — adding a step, splitting one too big for a single change, reordering, or laying out the next milestone. Use when a roadmap step needs splitting or sequencing, when asked what comes next or in what order, when moving a feature from the PRD onto the roadmap, or when a step has no spec yet and its scope is unclear. Not for marking progress — a row's state changes with the work that moves it.
---

# Roadmap planner

`docs/ROADMAP.md` says where the work stands and in what order it happens. Its
own header holds the rules — what a row is, the states, when a row is deleted —
so read it first and follow it; nothing here restates it.

**This skill changes the shape of the roadmap, never its progress.** Adding,
splitting, reordering and renumbering steps, and the ordering notes that justify
them, are yours. The State and Branch columns belong to the work: the
`orchestrator` skill and the branches that build each step move them.

## Two kinds of reason order a roadmap

| Kind | Example from the ordering notes | Who decides |
|---|---|---|
| **Technical** — a step needs what another builds, or both change the same thing | "Insights waits for the analytics library: its graph calls every library function" | Established by the `roadmap-deps` agent; you state it |
| **Product** — what users get first, what is worth shipping when | "CSV import includes AI categorisation: an import arrives categorised" | The user |

When the technical dependencies leave more than one valid order, or a split
changes what users get and when, the choice is the user's. Ask with
`AskUserQuestion` **before** editing: one option per order, each saying what
users get first and what it costs technically. A recorded decision in a doc
(the PRD's decisions table, a data-model decision) changes only on the user's word,
in that doc.

## The flow

1. Read the roadmap header and rows, the PRD sections and the feature docs the
   steps link to.
2. Dispatch the `roadmap-deps` agent with the step numbers and the question
   (what does each need, can any run in parallel). It reads the data model and
   the code so your context does not have to.
3. Put its **Decisions for the user**, and any product choice from the table
   above, to the user.
4. Show the edit — the new or changed rows and ordering notes — and write it
   only once the user agrees.

## A good step

- **One change, one PR**, shipping its tables, routes and screens together, and
  demoable on its own — not a backend step followed by a frontend step.
- **New rows** start `not started`, branch `—`, and their last column links the
  behaviour and the schema and says "No spec yet", as the existing rows do.
- **Sub-steps** take a letter (`5a`, `5b`), so nothing else renumbers. Before
  renumbering anyway, grep the repo for references to the old numbers.
- **Each ordering decision gets one bullet** in the ordering notes, saying which
  kind of reason it is and, for a technical one, what breaks if the order flips.
  When `roadmap-deps` finds steps that can run in parallel, say so there too —
  it is what the `orchestrator` reads.

## Common mistakes

| Mistake | Instead |
|---|---|
| Choosing between two sound orders yourself and presenting it as decided | Ask, with the cost of each |
| Editing a State or Branch cell, or noting progress anywhere but a row | Leave progress to the work |
| A row that is really two PRs, or a design spec in a row | Split it; the spec is written when the step starts |
| An ordering note that restates the row | Say why this order, and what breaks otherwise |
