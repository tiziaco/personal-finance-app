---
name: orchestrator
description: Coordinating two or more roadmap steps built at once, each by its own Claude Code worker session in its own worktree and iTerm2 tab, from one coordinator session in the main checkout. Use when asked to launch or dispatch workers, run steps or plans in parallel sessions, act as the coordinator, check on workers, handle a message from a worker, or merge branches that were built in parallel.
---

# Orchestrator

The coordinator is an ordinary session in the main checkout, named
`orchestrator` (`claude -n orchestrator`, or `/rename orchestrator`). It owns
what spans the steps: which run together, who owns what, launching the workers,
the roadmap rows, and the merge order. A worker owns its step end to end — the
spec, brainstormed with the user in its own tab, the plan, the execution, the PR.
The user talks to a worker in that worker's tab; the coordinator is not a relay.

Nothing the coordinator needs lives only in its context. A fresh coordinator
rebuilds the picture from the `in progress` rows of `docs/ROADMAP.md`,
`git worktree list`, each worktree's plan checkboxes in `.superpowers/plans/`,
and `ListAgents`.

## Channels

| To do this | Use | Never |
|---|---|---|
| Tell a worker something | `SendMessage` to its session name | `it2 session send`/`run` into its tab — that types into the user's input box |
| Hear from a worker | Its `SendMessage` to `orchestrator`, which wakes you | A polling loop, a watcher script, status files, the tab title |
| Hear that an executing worker stopped | Once its "executing" message arrives, one `SendMessage` with `notify_when_idle: true` and no message. A notice with no "PR open" behind it means it stopped mid-plan: look, and tell the user which tab | Subscribing during brainstorming, where a worker goes idle after every question |
| See what a worker is doing | `it2 session read -s <id>`, to look only | Treating screen text as a signal |

A session holds messages from a session in a different permission mode for its
user's approval. Launch every worker in the coordinator's own mode.

## Before launching

1. **The main checkout is on a clean `main`.** If it is not, another session is
   probably working there: ask the user, never switch it.
2. Dispatch the `roadmap-deps` agent with the steps. Launch only on `parallel` or
   `parallel with conditions`; put its **Decisions for the user** to the user
   first. Keep its Ownership paragraphs and conditions for the briefs.
3. On `main`, set each step's row to `in progress` with its branch, in one
   commit, so every worker branch starts from it. Ask before pushing `main`.

## Launching a worker

Cut its branch from `main` explicitly, then create the worktree on it —
`make worktree-new` cuts a new branch from whatever HEAD it runs at, and checks
out an existing one as is (the `worktrees` skill has the slots and options):

```bash
git branch feat/<name> main && make worktree-new NAME=<name>
```

Write the brief to `<worktree>/.superpowers/BRIEF.md` — gitignored, never
committed — then open its tab:

```bash
before=$(it2 ls | cut -f1 | sort)
it2 tab new --command "/bin/zsh -lc 'cd <worktree> && claude -n <name> --permission-mode <mode> \"Read .superpowers/BRIEF.md and follow it.\"'"
comm -13 <(echo "$before") <(it2 ls | cut -f1 | sort)   # the worker's session id
```

`it2 tab new` prints only a tab number; the session id is what `it2 session read`
and `it2 session close` take, so keep it.

**The brief**, in this order:

1. **The step** — its roadmap row, the branch and worktree, and which other steps
   are being built beside it, by which worker names. Workers do not message each
   other; anything that crosses goes to `orchestrator`.
2. **Read first** — the row's "Where it is specified" links. Do not summarise
   them.
3. **Ownership** — the `roadmap-deps` paragraph for this step and the
   conditions, verbatim.
4. **The workflow** — `superpowers:brainstorming` with the user in this tab, the
   spec in `.superpowers/specs/`; `superpowers:writing-plans`, the plan in
   `.superpowers/plans/`, approved by the user before it runs;
   `superpowers:subagent-driven-development`; then
   `superpowers:finishing-a-development-branch` up to an open PR, never a merge.
   This worktree is already the isolation: skip any step that offers another.
   Before the PR, what lasts in the spec moves into the docs, and the spec, the
   plan and this step's roadmap row are deleted, per the roadmap's header.
5. **Reporting** — `SendMessage` to `orchestrator`, first line self-contained:
   when the plan is approved and execution starts, when blocked by something
   outside its ownership, and when the PR is open (with its URL). Product
   questions and approvals come from the user in this tab, never from the
   orchestrator.

## When a worker messages

- **Blocked by the other step's territory** — rule on it if the Ownership
  paragraphs settle it, and tell both workers. If they do not, it is the user's
  decision: ask, then tell both.
- **PR open** — merge it when the user says so. Each merge and each push to
  `main` is the user's to approve, every time; the original request to "get them
  merged" does not cover them.
- **After the first merge** — message the remaining workers to merge `main` into
  their branch: the second migration's `down_revision` is re-pointed and the
  contract regenerated, per the `worktrees` skill. Adjacent roadmap rows conflict
  textually; both deletions stand.

## Teardown

Once a step is merged and the user agrees: in its worktree `make worktree-clean`
(never `make clean`), then `git worktree remove` and delete the branch. The
worker's tab closes when its session ends, or with
`it2 session close -s <id> --force`.

## Common mistakes

| Mistake | Instead |
|---|---|
| A watcher script polling screens or files | Workers message you; you wake on the message |
| Typing into a worker's tab | `SendMessage` |
| Merging, pushing `main` or deleting branches because the request implied it | Ask each time |
| A brief that restates CLAUDE.md, the skills or the feature docs | Link them; the worker loads them itself |
| Answering a worker's product question | Tell the user which tab is asking |
| Workers in a different permission mode from the coordinator | The coordinator's mode, or every message waits for approval |
| `make worktree-new` from a checkout that is not on `main` | Cut the branch from `main` first |
