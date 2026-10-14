---
name: thermos
description: "Launch both thermo-nuclear review subagents in parallel, then synthesize their findings. Use for thermos, double thermo review, or combined bug/security and code-quality branch audits."
disable-model-invocation: true
license: MIT (see LICENSE)
metadata:
  source: https://github.com/cursor/plugins/tree/main/thermos
---

# Thermos

Run the two thermo review passes as parallel subagents, then synthesize their
results. The rubrics are the `thermo-nuclear-review` and
`thermo-nuclear-code-quality-review` skills; each subagent reads its own.

## Workflow

1. **Determine the scope** from the user request, a PR number, or the current
   branch. The base is the branch this one was cut from: `main`, unless the
   `docs/ROADMAP.md` ordering notes name another (until Cutover, that is
   `template-base`). For a PR, use its base (`gh pr view <n> --json baseRefName`).
   If the base is unclear, ask.
2. **Gather the diff** yourself with Bash — no subagent needed:
   `git diff --stat <base>...HEAD` and `git diff <base>...HEAD`. Include
   uncommitted changes (`git diff HEAD`) only when the user asks for them.
   Leave out generated files — `server/openapi.json` and
   `web-app/packages/api-client/src/generated/` — and lockfiles, but list them in
   the scope so reviewers know they moved.
3. **Launch both subagents in the same message** with the Agent tool, so they
   run concurrently:
   - `subagent_type: "thermo-nuclear-review-subagent"` for bugs, breakages,
     security, tenant isolation, devex regressions, feature-flag leaks, and other
     branch-audit risks.
   - `subagent_type: "thermo-nuclear-code-quality-review-subagent"` for
     maintainability, structure, file-size growth, spaghetti, abstractions, and
     codebase-health risks.
4. **Pass each the same scope**: base ref, branch, PR number if any, the
   `--stat`, and the diff under `### Git / diff output`. When the diff is over
   ~2000 lines, pass the `--stat` and the file list instead and tell them to
   read the diff per file. Ask each to return prioritized findings with
   `file:line` evidence.
5. **After both finish, synthesize**: findings first, deduplicated across
   reviewers. Weight overlapping findings more heavily, resolve disagreements
   with your own judgment — verify a contested finding in the code before
   keeping it — and keep summaries brief.

The subagents' reports are not shown to the user. Surface the unified verdict,
the highest-signal findings, and any remaining uncertainty; do not restate each
report wholesale.

The review changes nothing. Fixing findings is a separate step the user asks for.
