---
name: worktrees
description: Running a second, independent dev stack in a linked git worktree — creating one, its port slot, what init rewrites, tearing it down, and merging branches built in parallel. Use when running make worktree-new / worktree-init / worktree-clean, working inside .claude/worktrees/, picking up a PR branch to run side by side, or merging two branches that each added a migration.
---

# Parallel worktrees

Each linked git worktree can run its own dev stack — its own database (so its
own migrations), containers and ports — so two branches can be built at once.

```bash
make worktree-new NAME=feed             # .claude/worktrees/feed on feat/feed, initialised
make worktree-new NAME=x BRANCH=fix/x   # another branch name
cd .claude/worktrees/feed && claude
make docker-run-core                    # or natively: Dev: All in a VS Code window on the worktree

make worktree-clean                     # inside it, when done
cd ../../.. && git worktree remove .claude/worktrees/feed
```

`worktree-new` checks out an existing local branch, tracks one that exists only as
`origin/<branch>` (how you pick up a PR branch), and otherwise creates it from the
current HEAD. It then runs `make worktree-init` in the worktree — for a worktree
created some other way, run that yourself. `worktree-clean` stops the worktree's own
dev servers (matched by working directory, not port alone) and removes its
containers, database volume and images.

| Slot | Internal | Supplier | API | Postgres | Compose project |
|---|---|---|---|---|---|
| 0 (main checkout) | base | base | base | base | `COMPOSE_PROJECT_NAME`, else the directory name |
| N (1–9) | base + 10N | base + 10N | base + 10N | base + 10N | `<main's project>-<worktree dir>` |

Bases are the main checkout's `*_HOST_PORT`s in its root `.env`, defaulting to
3000 / 3002 / 8100 / 5434. `make worktree-init` (which `worktree-new` runs)
assigns the slot once, saves it as `WORKTREE_SLOT`, and writes the slot's ports,
`ALLOWED_ORIGINS` and `NEXT_PUBLIC_API_URL` into the worktree's env files. Every
make target and `Dev:` task then follows them.

- **Use `worktree-new`, not `claude --worktree`.** The latter names the branch
  `worktree-<name>`, bases it on `origin/main`, starts before init has run, and
  on exit deletes the folder without `worktree-clean`, stranding the slot's
  volume and images.
- **Monitoring and ngrok stay in main.** `make docker-run` refuses in a
  worktree; use `docker-run-core`. `make dev-tunnel` works from any checkout,
  one at a time.
- **Tear a worktree down with `make worktree-clean`**, not `make clean` or
  `rebuild`: those prune the build cache every checkout shares.
- **`ALLOWED_ORIGINS` is rewritten** by `worktree-init` to the slot's three
  origins; extra origins main lists are not carried over.
- **A fresh worktree database fills itself.** Users are provisioned on their
  first authenticated request, so no webhook needs to reach it. Tests never
  touch it — they run against a testcontainer.
- **Merging parallel branches.** Two branches that each add a migration off the
  same head leave Alembic with two heads: `cd server && uv run alembic merge
  heads -m "merge <a> and <b>"` after the second merge, and commit the result.
  Never hand-merge `server/openapi.json` or the generated client — take either
  side, run `make gen-contract`, and commit what it produces.
- **Several projects from this template on one machine?** Give each its own
  block of 100: set the `*_HOST_PORT`s in its root `.env`, and `ALLOWED_ORIGINS`
  and both `NEXT_PUBLIC_API_URL`s to match. Re-run `make worktree-init` in
  existing worktrees to move them along.
