# SDD ledger — plan: docs/superpowers/plans/2026-08-26-ws4-clerk-webhooks.md

Spec: docs/superpowers/specs/2026-08-26-ws4-clerk-webhooks-design.md (read)
Branch: feat/ws4-clerk-webhooks. Not a worktree — user's own feature branch, not main.

## Pre-flight conflict scan

### Shared-file pairs

| Tasks | Shared file | Produces vs consumes | Finding |
|---|---|---|---|
| T1 ↔ T2 | app/services/user/service.py | T1 adds erase_user(); T2 extracts the block at ":104-155" | DRIFT — T1's insertion shifts T2's line range |
| T1/T2/T3 ↔ T7 | app/services/user/service.py | T7 drops "the TODO at :171" | DRIFT — TODO is actually at 173 today, shifts further |
| T2 ↔ T3 | app/services/user/service.py | T2 extracts linker; T3 makes resolve_user pass Clerk ts | Clean — disjoint regions |
| T5 ↔ T6 ↔ T7 | app/services/clerk/webhooks/service.py | T5 creates registry; T6/T7 append registrations | Clean — strictly append |
| T5 ↔ T8 | tests/integration/api/test_webhooks.py | T5 creates; T8 appends | Clean — sequential |
| T4 ↔ T9 | .env.example | T4 = server/.env.example; T9 = repo-root .env.example | Clean — different files |
| T3 ↔ T6/T7 | repository signatures | T3 adds last_synced_at kwarg; T6/T7 pass it | Clean — T3 precedes |

### Per-task self-consistency

| Task | Tests vs code it specifies | Finding |
|---|---|---|
| T1 | mocks match erase_user's consumed interfaces | Clean — all verified present |
| T2 | linker tests vs extracted block | Clean — supplier_repository at app/services/user/supplier_repository.py, both methods exist |
| T3 | clerk_timestamp_to_datetime + repo kwargs | Clean |
| T4 | env-file steps | STALE — all three env files already carry CLERK_WEBHOOK_SIGNING_SECRET (user commits fa60bd1, later) |
| T5 | integration tests vs conftest fixtures | TWO DEFECTS — see F1, F2 |
| T6 | handler unit tests | Clean |
| T7 | membership tests; dual event-name registration | Clean |
| T8 | e2e tests | Inherits F1/F2 from T5 |
| T9 | compose service | Clean; --url flag form unconfirmed (noted in plan) |

### Verified consumed interfaces (all present)
- conversation_service.soft_delete_all_user_conversations — service.py:122
- supplier_repository.get_by_id / set_contact_id — app/services/user/supplier_repository.py
- user_cache.invalidate_user, User.anonymize_user, unlink_supplier_contact
- conftest fixtures: client, db_session, mock_agent, test_user — all exist
- No test asserts the log event `supplier_linked_on_jit`, so T2's rename breaks nothing

## Rulings (pre-flight)

Ruling: F1 — the plan's T5/T8 integration tests call `client.post(...)` without `await`,
  but `client` (tests/conftest.py:142) is an httpx AsyncClient. Every call must be awaited.
  Implementers of T5 and T8 will be told to await all client calls.
  — Why: unawaited, `response.status_code` raises AttributeError on a coroutine; the tests
    could not pass as written.
  — Cost if wrong: none; awaiting an AsyncClient is unambiguously correct here.

Ruling: F2 — the webhook route depends on ChatbotAgentDep (get_chatbot_agent), which the
  bare `client` fixture does not override, so the real agent factory would run inside the
  tests. T5 will add a `webhook_client` fixture to tests/integration/conftest.py layering
  mock_agent over `client` WITHOUT overriding get_current_user (the webhook route is
  deliberately unauthenticated, and overriding auth would mask a regression where the
  route accidentally starts requiring a JWT). T5/T8 use `webhook_client`.
  — Why: existing `authenticated_client_with_agent` bundles an auth override that would
    defeat the test asserting the endpoint needs no bearer token.
  — Cost if wrong: a redundant fixture; trivial to collapse later.

Ruling: F3 — all line-number references in the plan (T2 "service.py:104-155",
  T7 "service.py:171") are advisory. Tasks 1–3 shift them. Implementers locate targets by
  content, not line number.
  — Why: the referenced blocks are textually unambiguous.
  — Cost if wrong: an implementer edits the wrong region; the task review catches it.

Ruling: F4 — T4's env-file steps are already satisfied (server/.env.example:31,
  .env.development:34, .env.test:32, the last matching the plan's TEST_SECRET verbatim).
  T4's implementer verifies and does not duplicate the lines.
  — Why: the user set these up manually before execution began.
  — Cost if wrong: duplicate env keys; last-wins, harmless, visible in review.

Note (not a ruling): server/ carries BOTH pytest.ini and [tool.pytest.ini_options] in
  pyproject.toml with divergent asyncio_default_fixture_loop_scope. pytest.ini wins.
  Pre-existing, out of scope for WS4; flagged for the final review only.

## Progress

Task 1: implementer DONE_WITH_CONCERNS (commit 27a9fef; 331/331 pass, test_user_erasure 3/3 TDD RED->GREEN, test_auth_delete 5/5)
Task 1: Ruling: the implementer changed test_auth_delete.py's mocked_externals patch target
  (app.api.v1.auth.delete_user_memory -> app.services.user.service.delete_user_memory),
  diverging from my pre-flight ruling that the file pass "unchanged". Accepted.
  — Why: a patch target names the module where a symbol is USED. Moving the cascade into the
    service necessarily moves that target; the brief itself mandates dropping the auth.py
    import. The assertions — which are what encode behaviour — are untouched, so the file
    still proves behaviour is preserved. My "unchanged" wording was about assertions and was
    imprecise about patch targets.
  — Cost if wrong: if the patch target were wrong, the mock would not bind and the real mem0
    call would fire in tests; the suite passing at 331/331 with the delete tests green is
    evidence it binds. Low.
Task 1: review -> spec compliant, task quality NEEDS FIXES. 2 Important, 1 Minor.
Task 1: Ruling: Important-2, the log-event rename user_deleted_gdpr_compliant -> user_erased,
  is plan-mandated and STANDS. The reviewer is right that a structlog event name is observable
  behaviour and that "pure refactor" nominally forbids changing it.
  — Why: the event now fires from a shared service with two callers. Naming it after the HTTP
    route's semantics becomes actively wrong the moment the user.deleted webhook calls the same
    cascade. Reverting would bake a lie into the log stream for the sake of a rule whose purpose
    (don't silently change behaviour) is served better by renaming now, before anything depends
    on it, than by renaming later. WS4 is unreleased, so no dashboard or alert keys on it yet.
  — What the fix round DOES carry: server/docs/gdpr-compliance-guide.md:171 still shows the old
    name. Rename it there so this diff does not add to that doc's drift.
  — Cost if wrong: a log query somewhere keys on the old name and goes quiet. Grep found exactly
    one reference in the repo (the doc), so the blast radius is visible and small.
Task 1: minor (deferred): app/api/v1/auth.py:17 imports `logger`, now the file's only reference
  to it — genuinely dead (grep confirms no call sites). The brief said "Leave logger", and ruff
  globally ignores F401 (pyproject.toml:140) so lint stays green. Not entering the fix loop, per
  minors-never-extend-the-loop. Final review triages.
Task 1: minor (deferred): server/docs/gdpr-compliance-guide.md was ALREADY stale before this
  branch (cites a nonexistent app/services/user/api.py). Only the event-name line is in scope
  here; a full repair of that doc is out of scope for WS4.
Task 1: fix round 1/5 dispatched -> implementer DONE_WITH_CONCERNS (commit 8fcfaf5;
  test_user_erasure 4/4; new ordering test mutation-verified: reordered erase_user(), test
  failed, reverted, clean diff). Scoped re-review dispatched over 27a9fef..8fcfaf5.
Task 1: fix round 1/5 (2 addressed, 0 open; commits 27a9fef..8fcfaf5)
Task 1: complete (commits ffc92f5..8fcfaf5, review clean)
Task 2: implementer DONE_WITH_CONCERNS (commit e0e80f7; 341/341 full suite, incl. new
  idempotency test proving a second identical call is a true no-op).
Task 2: Ruling: the brief's code adds a log line the original inline block lacked —
  logger.warning("supplier_link_target_missing") when public_metadata names a supplier_id
  whose row does not exist. Plan-mandated; it STANDS.
  — Why: it is purely additive — no control-flow change, the path was and remains a no-op.
    Today that case fails silently, which is precisely the class of bug webhooks make worse
    (an invite carrying a stale supplier_id would link nothing and say nothing). "Pure refactor"
    exists to stop silent behaviour drift, not to forbid making an existing silent failure
    observable.
  — Cost if wrong: one extra warning line in logs for a case that should be rare. Negligible.
Task 2: env note: `make lint` / ruff is not runnable in this environment (binary absent from
  every dependency group). Implementer verified the production file via an ephemeral
  `uv run --with ruff ruff check`. Flagged for the final review — CI lint coverage for this
  branch is unproven locally.
Task 2: review -> spec compliant, task quality APPROVED. 0 Critical, 0 Important, 2 Minor.
  Reviewer traced both named risks equivalent by hand: metadata-merge precedence (top-level
  wins; first-membership-wins per key) and the relink guard + capture-before-overwrite +
  both cache invalidations. Idempotency test confirmed a genuine no-op proof
  (set_contact_id.await_count == 1 and invalidate.await_count == 1 after two calls).
Task 2: Ruling: resolved the reviewer's one "cannot verify from diff" item myself — a replay
  carrying replace:True still performs a redundant set_contact_id write and an unconditional
  self-invalidate. NOT a gap; no fix.
  — Why: the spec defines idempotent as state-convergence, not side-effect-freedom. The
    redundant write sets contact_id to the value it already holds, and a cache INVALIDATION is
    unconditionally safe (worst case one extra DB read; only populating before commit is
    unsafe). The load argument does not apply: replace:True is an admin-initiated re-link from
    the Clerk dashboard, human-scale volume, not a hot path. Behaviour is also unchanged from
    pre-refactor, so this task is not where it would be litigated.
  — Cost if wrong: under a replay storm, extra DB reads. Bounded and observable.
Task 2: minor (deferred): app/services/user/service.py:263 — the extraction dropped the inline
  comment explaining why the unconditional invalidate_user(user_id=user.id) is NOT dead on the
  pure-JIT path (create_or_get's race branch can return an existing user holding a cached None
  from an earlier 403). With three callers arriving in Tasks 6-7, a maintainer could delete the
  line as redundant and reintroduce a stale-cache bug. Worth restoring one line of rationale.
Task 2: minor (non-issue): test file at tests/unit/services/test_supplier_linking.py rather than
  tests/unit/services/user/. Plan-mandated AND matches the repo's existing flat convention
  (test_user_cache.py sits there). No action.
Task 2: complete (commits 8fcfaf5..e0e80f7, review clean)
Task 3: implementer DONE (commit 83fab7d; 8/8 new, 349/349 full suite; no concerns)
Task 3: review -> spec compliant, task quality APPROVED. 0 Critical, 0 Important, 2 Minor.
  Reviewer independently verified all three named risks: tz-awareness (fromtimestamp(v/1000,
  tz=UTC), test asserts tzinfo separately from value), ms-vs-s unit correctness (recomputed the
  expected value via divmod rather than reusing the impl's arithmetic), and the non-null
  fallback in every changed path. No Alembic migration present, per the org_id ruling.
Task 3: Ruling: resolved the reviewer's "cannot verify from diff" item myself — whether
  clerk_user.updated_at actually exists on the Clerk SDK object. It does: clerk_backend_api/
  models/user.py:221 declares `updated_at: int`, REQUIRED and non-nullable. So the
  getattr(..., None) default never fires in production and the guard rests on Clerk's clock as
  intended. No gap, no fix.
  — Cost if wrong: if a future SDK major made the field optional, the getattr default would
    silently restore the local-clock bug this task exists to kill. Low now; worth a pin if the
    SDK is ever upgraded.
Task 3: minor (deferred): app/utils/clerk.py:26 excludes bool (guarding int-subclass footgun)
  but no test passes True/False. One-line test would close it.
Task 3: complete (commits e0e80f7..83fab7d, review clean)

## Constraint discovered for Task 4 (from app/exceptions/handlers.py:58-68)

The centralized ServiceError handler puts `exc.context` into the RESPONSE BODY as `details`,
and `exc.message` as `message`. Both reach an UNAUTHENTICATED caller for a webhook 401.
Consequences that bind Task 4:
  - Exception kwargs are attacker-visible. Never pass anything derived from the signing
    secret, the computed HMAC, the payload body, or which specific check failed.
  - The handler reads exc.status_code generically, so WebhookPayloadTooLargeError with
    status_code = 413 needs NO new base class and NO handler change, even though 413 is absent
    from the documented hierarchy in server/CLAUDE.md.
Task 4: implementer DONE_WITH_CONCERNS (commits 64b971c, 3a72473; 22 adversarial unit tests,
  371 full suite, 0 warnings; size-before-HMAC ordering mutation-tested).
Task 4: Ruling: PLAN DEFECT confirmed and the implementer's deviation ACCEPTED. The plan's
  dependency code was written against svix 1.x: `payload = Webhook(secret).verify(body, headers)`
  then `ClerkEvent.model_validate(payload)`. I verified the installed svix 2.1.0 myself —
  svix/webhooks.py:14 annotates `verify(...) -> None` and delegates with `json_parse=False`, so
  the plan would have validated None. The implementer discards the return and decodes the
  already-verified bytes inside the same try.
  — Why accepted: it is the only correct adaptation, and it strictly improves the security
    posture — malformed JSON now collapses into the same opaque 401 rather than escaping as a
    different error class.
  — Cost if wrong: none; the alternative does not work at all.
Task 4: Ruling: the empty-secret path yielding a generic 500 (while a malformed secret yields
  401) is ACCEPTED as-is; no runtime check added.
  — Why: verified in standardwebhooks/webhooks.py:34-39 — an empty secret raises
    EmptyWebhookSecretError (not a ValueError, so it escapes the except and 500s), while a
    malformed one dies in base64.b64decode raising binascii.Error, which IS a ValueError and so
    becomes the opaque 401. BOTH fail closed; neither admits a request. In Docker the empty case
    is unreachable — REQUIRED_ENV_VARS stops the container before it serves. Outside Docker it
    surfaces as loud 500s, which is the correct failure for a misconfigured operator. Adding a
    check was ruled out during design: presence is a startup concern, not a per-request one.
  — Cost if wrong: a self-hosted dev running outside Docker with no secret sees 500s instead of
    a clear startup error. Loud and diagnosable.
Task 4: Ruling: `size=len(body)` as the sole exception kwarg reaching a caller on the 413 is
  NOT a leak. The caller already knows the size of the body it just sent. Kept verbatim.
Task 4: review -> spec compliant, task quality APPROVED with 1 Important, 3 Minor.
  Security assessment clean on every axis that matters: no signature-bypass path (verified bytes
  and parsed bytes provably identical, same local `body`, same try block); no failure reads as
  success; every rejection collapses to one byte-identical 401 with empty context that the
  handler drops via exclude_none; no secret/HMAC/payload data in any log line (reviewer checked
  the non-obvious vector — pydantic ValidationError.__str__ embeds offending input, but
  handlers.py:48-56 logs 4xx without exc_info, so it never renders); size-before-HMAC ordering
  pinned by a test that would genuinely fail on a swap.
Task 4: Ruling: resolved both "cannot verify from diff" items myself, both no-gap.
  (a) docs/setup/clerk-webhooks.md DOES exist — at repo root (6130 bytes, commit a1816b3). The
      reviewer searched server/-relative and correctly reported not-found from where it stood.
  (b) server/.env.example:31 carries the placeholder; .env.test's secret decodes to 24 valid
      base64 bytes, so svix can construct a Webhook from it in Task 5's integration tests.
Task 4: Ruling: Important-1 (size cap bounds the HMAC but NOT memory) is REAL and enters the fix
  loop. My plan wrote both the flawed code and the comment that overstates it.
  — Why fix rather than park: the reviewer verified nothing upstream bounds the body — uvicorn
    launched without --limit-max-request-size (Dockerfile:93), no body-size middleware among the
    six in main.py:115-133, no reverse proxy in the compose stack. Combined with the deliberate
    absence of a rate limit on this route, an unauthenticated caller can force multi-GB
    allocation, repeatedly. Availability-only — it admits no unsigned request — but this is the
    one route on the app reachable with no credential at all.
  — Why the fix is a STREAMING cap, not just a Content-Length pre-check: Content-Length alone is
    defeated by chunked transfer-encoding, and the threat model here is a deliberate attacker,
    not an oversized-but-honest client. A header check that an attacker skips by omitting the
    header is theatre.
  — Cost if wrong: reading the body via request.stream() rather than request.body() is a slightly
    less common idiom; if it interacts badly with the TestClient the integration tests in Task 5
    would surface it immediately.
Task 4: fix round 1/5 -> implementer DONE (commit ff548f4; 25 webhook unit tests, 374 full
  suite, 0 warnings, ruff clean). _read_body_capped() accumulates request.stream() and raises
  the 413 BEFORE appending the chunk that crosses the cap. Mutation-verified: restoring the
  buffer-then-measure shape fails both NEW tests on byte count, while the PREVIOUS round's two
  status-only oversized tests still pass under that same mutant — which is precisely why the
  byte-count assertion was the necessary one. Third test proves chunked reassembly does not
  corrupt the signed artifact.
Task 4: note for deployment (not actioned): the cap bounds what the APP retains, not network
  ingress. --limit-max-request-size on uvicorn, or a reverse proxy, is the right place for that.
  Carry into the final review.
Task 4: fix round 1/5 (1 addressed, 0 open; commits 3a72473..ff548f4). Re-review confirmed:
  same-object verify/parse identity preserved (single `body` local passed to both), cap still
  exclusive at exactly MAX_WEBHOOK_BODY_BYTES, stream consumed once, and the new tests assert a
  live delivered-bytes counter rather than status alone — genuinely distinguishing the fixed
  shape from the buffer-then-measure mutant.
Task 4: minor (deferred): InvalidWebhookSignatureError extends AuthenticationError but NOT
  WebhookError, so `except WebhookError` silently misses the exception that fires on every
  attack. Carry a pointer into Task 5's dispatch — that is the task that might write such a
  handler.
Task 4: minor (deferred): test_an_unusable_signing_secret_fails_closed contains a vacuous
  assertion (`bad_secret not in str(...) or not bad_secret` is unconditionally true for "").
Task 4: minor (deferred): WebhookError (400) is never raised directly; it exists only as the
  base of the 413. Not dead code — noting so nobody deletes it.
Task 4: complete (commits 83fab7d..ff548f4, review clean)
Task 5: implementer DONE (commit 18caba1; 6/6 new webhook tests RED->GREEN, 380 full suite,
  0 warnings).
Task 5: Ruling: the brief's Step-6 test asserted status 500 for a failing handler; the
  implementer substituted pytest.raises(RuntimeError). ACCEPTED.
  — Why: I verified the cause is pre-existing and already documented in this repo at
    tests/integration/exceptions/test_handlers.py:107-109 — Starlette's BaseHTTPMiddleware
    (pulled in by the Prometheus middleware) re-raises route exceptions via call_next before
    FastAPI's handler layer runs, so over ASGITransport no handler-produced response exists to
    assert on. The existing codebase already works around this the same way. The brief's
    assertion could not have passed.
  — Cost if wrong: the test proves the exception propagates rather than proving the HTTP status
    Clerk observes. See the open question below, which I have routed to the reviewer.
Task 5: OPEN QUESTION routed to reviewer — does a raising handler actually yield a non-2xx to
  Clerk in PRODUCTION, and is it logged? The design depends on it: a failing handler must make
  Clerk retry. Under uvicorn an escaped exception becomes a plain 500, which satisfies retry.
  But because BaseHTTPMiddleware re-raises BEFORE global_exception_handler, the app's own
  structured logging and correlation-id error body never fire — uvicorn logs it instead. For a
  webhook that is an observability gap precisely where it hurts: a silently failing handler.
  Pre-existing and app-wide, not introduced here.
Task 5: review -> spec compliant, task quality APPROVED. 0 Critical, 0 Important, 3 Minor.
  Reviewer verified the full route chain (main.py:144 -> api.py:20 -> webhooks.py:31), the
  registry as a real mapping, the unregistered-type no-op, and — notably — checked the RLS
  docstring for ACCURACY rather than mere presence, tracing AuthMiddleware.dispatch (auth.py:29
  sets request.state.user_id = None unconditionally) and get_db_session (database.py:48-49
  passes that None to set_session_context). The tests exercise the real svix HMAC path with no
  dependency override, and separate "unregistered -> 204" from "handler raises -> propagates".
Task 5: RESOLVED (my open question, answered against installed Starlette source): my concern was
  WRONG. Starlette extracts the Exception/500 handler out of the handler map and makes it
  ServerErrorMiddleware — the OUTERMOST layer, wrapping every user middleware including the
  Prometheus BaseHTTPMiddleware. On a raising handler it DOES run global_exception_handler,
  DOES send the 500 (response_started is False at that point), and only THEN re-raises so the
  server can log. logger.exception("unhandled_exception") fires with the correlation id
  auto-injected by the logging processor. Uvicorn sees response_started=True and does not
  double-send; transport.close() flushes the queued 500 first, so Clerk receives a complete 500,
  not a reset connection. No observability gap. Nothing to carry to the final review.
Task 5: minor (deferred): service.py:20-24 mixes typing.Dict with builtin dict in a 3.13
  codebase; service.py:53 docstring's "It must not raise" reads ambiguously out of context.
Task 5: complete (commits ff548f4..18caba1, review clean)
Task 6: implementer DONE (commit 04ed5c7; 13/13 new unit tests, 393 full suite, 0 warnings). Ordering guard mutation-verified twice (< -> <= and < -> >), each breaking exactly its intended test.
Task 6: review -> spec compliant, task quality APPROVED. 0 Critical, 2 Important, 6 Minor.
  Both invariants confirmed to HOLD by code reading, and the reviewer independently judged that
  the two claimed mutations would genuinely fail their named tests (<= would fire the guard on
  the same-timestamp test; > would let the stale write through). Never-resurrect verified
  structurally: the module's only create_or_get is textually inside handle_user_created's
  `if user is None` branch, so handle_user_updated cannot reach it, and the test asserts on
  create.assert_not_awaited() rather than a return value.
Task 6: Ruling: Important-1 (email in a log line) ENTERS THE FIX LOOP rather than deferring.
  app/services/user/repository.py:112 does logger.info("user_created", ..., email=email, ...).
  — Why not defer: it is pre-existing, but Task 6 is what newly routes CLERK WEBHOOK payload
    emails into it, which is exactly what the never-log-PII constraint exists to prevent. This
    is a GDPR-sensitive codebase with its own erasure guide; shipping a known email-in-logs leak
    because it technically predates the diff would be the wrong call. Task 3's commit is on this
    branch, so it is in scope. One-line fix.
  — Cost if wrong: a log line loses a field operators may have used for debugging. clerk_id and
    user_id remain, so the record is still traceable.
Task 6: Ruling: Important-2 (host clock can contaminate the guard's stored operand) ENTERS THE
  FIX LOOP. repository.py:210 does `user.last_synced_at = last_synced_at or now` with
  now = datetime.now(UTC). _apply_profile passes event_ts, which is None whenever the payload
  lacks a usable updated_at — so one such event writes a HOST-CLOCK value into last_synced_at,
  and every subsequent legitimate Clerk event is then compared against it.
  — Why fix: that is precisely the freeze failure mode Task 3 exists to prevent, reintroduced
    through a side door. The comparison is never against a local clock, but the stored operand
    can become one, which is just as corrupting.
  — Fix shape ruled: keep the repository fallback (the JIT path genuinely has no Clerk timestamp
    and needs it). Change the WEBHOOK path only — when event_ts is None, preserve the row's
    existing last_synced_at instead of advancing it to now(). Contained to Task 6's file, no
    change to Task 3's contract.
  — Cost if wrong: a webhook with no updated_at leaves last_synced_at untouched, so a later
    stale event could apply. Strictly better than freezing the row forever.
Task 6: minor (deferred): repository.py forces email_verified=False when the primary address is
  unresolvable, silently flipping a verified user to unverified while preserving email.
Task 6: minor (deferred): USER_PAYLOAD lists the primary address FIRST, so the primary-email
  tests would also pass an index-0 implementation — the exact bug the brief called out. A
  one-line fixture reorder would make them real discriminators.
Task 6: minor (deferred): test_no_handler_populates_the_role_cache exercises only
  handle_user_updated despite its name; the other two handlers are unverified by it.
Task 6: minor (deferred): link_supplier_from_metadata runs even when the ordering guard dropped
  the event; benign today via the callee's own idempotence guard, but a stale created-replay
  carrying `replace` would act on stale metadata.
Task 6: minor (deferred): test functions lack return annotations (plan-mandated, brief verbatim).
Task 6: fix round 1/5 -> implementer DONE (commit 12b7f39; 19 focused, 394 full suite, ruff clean). Both mutation checks re-confirmed.
Task 6: fix round 1/5 (2 addressed, 0 open; commits 04ed5c7..12b7f39). Re-review confirmed the
  JIT fallbacks in BOTH create() and update_from_clerk() survived untouched, the strict `<`
  guard and its Clerk-sourced operands are byte-for-byte unchanged, and the new test asserts on
  the VALUE passed (update.await_args.kwargs["last_synced_at"] == stale_synced_at) rather than
  merely that the call happened. PII fix confirmed narrow — only the email kwarg removed.
Task 6: complete (commits 18caba1..12b7f39, review clean)
Task 7: implementer DONE (commit d1c5d4c; 11/11 new, 405 full suite).
Task 7: review -> spec ISSUES FOUND, task quality NEEDS FIXES. 0 Critical, 3 Important, 5 Minor.
  Correct and verified: missing-antecedent create from public_user_data, dual-cache invalidation
  on .deleted (reviewer checked cache.py:160-190 confirming org role keys on clerk_id and
  supplier link on user_id, so both args are needed), role propagation via invalidation (the
  role is not a column — resolve_org_role reads the cache, so invalidation IS the propagation),
  PII-clean across all nine log calls (email is bound and threaded into create_or_get but never
  logged), zero try/except so everything propagates, and every cross-module call signature
  verified against the real implementation rather than against a mock.

Task 7: Ruling: Important-1 ENTERS THE FIX LOOP. PLAN DEFECT, and a serious one.
  membership_handlers.py:82 passes last_synced_at=clerk_timestamp_to_datetime(data["updated_at"])
  on the create path — but that is the MEMBERSHIP's clock, while User.last_synced_at is the
  ordering clock for USER events. A membership is created after its user, so
  membership.updated_at > user.updated_at. When user.created then lands, handle_user_created
  finds the row, routes to _apply_profile, and the guard `event_ts < user.last_synced_at` DROPS
  the real user payload as stale.
  — Why this is bad: it defeats the entire purpose of the missing-antecedent path. Reversed
    delivery is the common case this code exists for, not an edge. The module's own comment
    ("Start false; user.created or user.updated corrects it") and its docstring principle that
    reusing last_synced_at "would conflate two unrelated clocks" are both falsified by line 82.
  — Fix shape ruled: seed last_synced_at with the EPOCH (1970-01-01 UTC), not the membership
    timestamp and NOT None. None is worse — create() falls back to datetime.now(UTC)
    (repository.py:105), which is newer still and drops even more. Epoch is semantically honest:
    this row has never been synced from a user event, so any genuine user event must win.
  — Cost if wrong: until the first user.* event lands, the row has no ordering protection and a
    stale user event could apply. That is correct — you cannot order against a clock you have
    never had. Bounded: the reviewer grepped and found email_verified has no authorization
    consumer, so today's blast radius is stale profile data, not an auth defect.

Task 7: Ruling: Important-2 ENTERS THE FIX LOOP. membership_handlers.py:189-193 acts on ANY
  membership deletion without checking the event's org is the user's current org.
  — Why: an admin moving a user between orgs emits created(B) and deleted(A) with no ordering
    guarantee (repository.py:223-224 names this reassignment scenario explicitly), and there is
    deliberately no ordering guard on this path. If deleted(A) lands second the user loses org B.
    JIT repairs org_id from the JWT, but JIT does NOT restore Supplier.contact_id — so the
    spurious unlink is PERMANENT and recoverable only by re-invitation.
  — This is distinct from the accepted offboarding decision. Unlinking on a genuine offboarding
    is the user's chosen product behaviour; unlinking on the WRONG org's deletion event is a bug.
  — Fix shape ruled: guard on `_organization_id(data) not in (None, user.org_id) -> return`.
  — Cost if wrong: a legitimate deletion is skipped when the user's org_id was never set. Safer
    failure than a permanent unlink, and self-heals at next login.

Task 7: Ruling: Important-3 ENTERS THE FIX LOOP. The dispatch test parametrizes only .created
  over both spellings (2 of 6 keys) and asserts merely `is not None`.
  — Why: the dual-spelling registration exists SPECIFICALLY because a wrong key fails silently.
    A typo or a swapped handler on the .updated/.deleted lines would ship green. I read
    service.py:91-95 and the mapping is correct today — but nothing guards it, and the guard is
    the whole point. Assert all six keys resolve to the three expected function objects.
Task 7: fix round 1/5 -> implementer DONE (commit 174e67e; 413/413, 8 new regression tests). All three fixes revert-verified individually.
Task 7: fix round 1/5 (3 addressed, 0 open; commits d1c5d4c..174e67e). Re-review confirmed:
  _UNSYNCED = datetime(1970,1,1,tzinfo=UTC) survives create_or_get -> create WITHOUT hitting the
  `or datetime.now(UTC)` fallback (a datetime has no __bool__ override, so it is truthy); the
  cross-module test drives BOTH handlers in sequence through _apply_profile's real comparison
  rather than mocking the comparison; the org guard skips correctly when user.org_id is None and
  does NOT skip the matching-org case, so genuine offboarding still unlinks; and the dispatch
  test now asserts handler IDENTITY across all six keys.
Task 7: minor (deferred, UPDATED): test_deleted_is_idempotent now exercises the org guard's
  early-return path rather than the original "acts and finds nothing to do" path. Its assertion
  still holds either way, which is precisely why it was already flagged as asserting nothing the
  handler could fail. The deferral now covers a test that is not testing what its name claims.
Task 7: complete (commits 12b7f39..174e67e, review clean)
Task 8: implementer DONE (commit b206aa2; 14/14 in test_webhooks.py, 421 full suite; testcontainers DB started cleanly; two tests mutation-checked against reverted production code; no new defect found).
Task 8: review -> spec compliant, task quality APPROVED. 0 Critical, 0 Important, 4 Minor.
  Reviewer verified all 24 client call sites are awaited, all 8 new tests use webhook_client
  (never the auth-overriding fixture), and — the check that mattered — went test by test naming
  what production change would make each one fail. None would pass against a stubbed handler.
  The org-mismatch test correctly asserts the SUPPLIER LINK survived, not just org_id: the
  supplier unlink was the permanent-damage vector, org_id self-heals via JIT.
Task 8: minor (deferred): replay test uses two different svix-ids rather than one identical
  request. Functionally equivalent — nothing dedupes on svix-id, so idempotency is data-driven.
Task 8: minor (deferred): no integration test for the POSITIVE unlink path (matching-org
  deletion actually clearing Supplier.contact_id); only the mismatch no-op case is covered.
Task 8: minor (deferred): email_verified not asserted cleared in the erasure test.
Task 8: minor (deferred): camelCase dispatch keys have no direct integration test.
Task 8: complete (commits 174e67e..b206aa2, review clean)
Task 9: implementer DONE (commit 39ebf41; docker compose config exit 0, ngrok block renders).
Task 9: Ruling: PLAN DEFECT confirmed — my pre-flight flag was right. The brief's
  `command: http server:8000 --url=${NGROK_DOMAIN}` was the one wrong combination. The
  implementer verified against the actual image (`docker run --rm ngrok/ngrok:latest http --help`)
  that `--domain` DOES NOT EXIST in ngrok/ngrok:latest and `--url` REQUIRES a scheme. Corrected
  to `--url=https://${NGROK_DOMAIN}`, keeping NGROK_DOMAIN bare — which is how it is stored in
  the user's env file and documented at docs/setup/clerk-webhooks.md:40. ACCEPTED.
  — Cost if wrong: none. Verified against the image rather than reasoned about.
Task 9: Ruling: keep the PLAIN service; do NOT add a compose `profiles:` key. I asked the
  question and the empirical answer settles it.
  — Evidence: with NGROK_AUTHTOKEN empty the container exits ONCE with code 1 and stays exited
    (no `restart:` key, and Compose's default policy is `no`), failing fast with a named
    ERR_NGROK_4018. Zero effect on server, db, or the portals.
  — Why not profiles: it would either silently never start ngrok until someone passes
    --profile by hand — defeating the setup doc's "brings up ngrok with the stack" promise —
    or force a conditional into the Makefile, a real behavioural branch to maintain. The
    failure is already cheap and legible; the complexity is not earned.
  — Cost if wrong: a developer with no ngrok account sees one exited container in `docker ps -a`.
Task 9: NOTE for review — the ABSENCE of a `restart:` key on the ngrok service is deliberate and
  load-bearing, and it is inconsistent with its siblings (server has on-failure:5, db and the
  portals have `always`). Anyone "fixing" that inconsistency by adding `restart: always` would
  convert a single clean exit into a restart storm for every developer without a token.
Task 9: review -> spec compliant, task quality APPROVED. 0 Critical, 0 Important, 1 Minor.
  Reviewer independently confirmed docker-compose.prod.yml untouched and ngrok-free, the tunnel
  targets server:8000 (not localhost), NGROK_AUTHTOKEN is interpolated not hardcoded, no
  restart: key was added, and --url=https://${NGROK_DOMAIN} is internally consistent with the
  setup doc's bare-hostname format at :40 and its scheme-at-point-of-use pattern at :78. Also
  noted the in-file comment explaining the https:// prefix, which stops a future maintainer
  "fixing" it back to the brief's broken literal.
Task 9: minor (deferred): the ngrok service uses mapping-style `environment:` while the rest of
  the file uses list style. Valid either way, no behavioural difference.
Task 9: complete (commits b206aa2..39ebf41, review clean)

=== ALL 9 TASKS COMPLETE ===

=== FINAL WHOLE-BRANCH REVIEW ===
Verdict: Ready with noted fixes. 0 Critical, 3 Important, 11 Minor. All five invariants assessed
  as holding (ordering with one leak = Important 1). Deferred-minor triage: 2 of 20 must-fix.

Ruling: Important-2 is a CORRECTION TO MY OWN TASK 7 RULING. I prescribed the guard shape
  `if _organization_id(data) not in (None, user.org_id): return`. That is too broad: when
  user.org_id is already NULL, ANY event org fails the test and the handler returns before
  unlinking the supplier. Reachable path — a supplier is invited, user.created inserts the row
  with org_id=None BY DESIGN and links the supplier from public_metadata, the
  organizationMembership.created that would have set org_id is lost, the user is later removed
  from the org, and membership.deleted no-ops. The supplier keeps an offboarded contact, and per
  the spec's own D-5 reasoning JIT cannot repair contact_id — it is PERMANENT.
  — I fixed one direction of this bug in Task 7 and opened the other. Narrowing to
    `if event_org_id and user.org_id and event_org_id != user.org_id: return` preserves the
    reassignment protection exactly (that case cannot arise when org_id is NULL, because
    created(B) would have set it) and stops swallowing genuine offboardings.
  — Cost if wrong: none identified; strictly narrower than the current guard.

Ruling: Important-1 ENTERS THE FIX WAVE. handle_user_created's INSERT branch passes
  last_synced_at=event_ts, which is None when updated_at is unusable, and repository.py:106 then
  substitutes datetime.now(UTC) — the exact contamination _apply_profile and _UNSYNCED both
  exist to prevent, in the one branch that breaks the rule. Fix: `event_ts or _UNSYNCED`, with
  _UNSYNCED hoisted into app/utils/clerk.py so both handler modules share one definition.

Ruling: Important-3 ENTERS THE FIX WAVE. test_deleted_is_idempotent exits at the org-mismatch
  guard rather than the replay path its name claims, and its only assertion is true on entry.
  It is the ONLY test covering membership-deleted idempotency and it is the test that would have
  caught Important 2. Its emptiness is why that bug survived nine reviews.

Ruling: HOLDING my Task 9 no-profiles ruling despite the final review recommending
  `profiles: ["tunnel"]`. The empirical evidence stands: one clean exit, no restart loop, zero
  effect on the core stack, and a profile would either silently never start ngrok — defeating the
  setup doc — or force a Makefile conditional. ACCEPTING the documentation half: the root
  CLAUDE.md service table and `make help` still omit ngrok, which is a real inconsistency.

Ruling: Minor-11 (get_db_session logs str(e) on IntegrityError, rendering SQLAlchemy's
  `[parameters: ...]` including the email) ENTERS THE FIX WAVE despite being pre-existing on every
  write path. Same class as the Task 6 email-in-logs finding I already ruled must-fix; WS4 adds a
  new UNAUTHENTICATED way to reach it. Scoped tightly to the log line only.

=== FIX WAVE INTERRUPTED BY USER ===
The final-review fix-wave agent was STOPPED BY THE USER mid-work. State at interruption:
  - HEAD still 39ebf41; NOTHING committed by the fix wave.
  - Working tree DIRTY: 12 modified files, uncommitted.
  - No final-fix-report.md was written, so there is no record of what was completed vs started.
  - The uncommitted edits are UNREVIEWED and UNVERIFIED — no test run is known to have completed.
Do NOT resume without the user's instruction. Do NOT discard the working tree without asking:
  it may contain most of the fix wave's work.
Outstanding at interruption: 3 Important + 5 must-fix/cheap Minor + 2 doc items from the final
  whole-branch review. All are enumerated above in the final-review rulings section.
CORRECTION: the fix wave was NOT stopped by the user — it was an environment failure. Resumed.
Assessed partial state by inspection before re-dispatching:
  DONE by the interrupted agent: _UNSYNCED hoist + `event_ts or _UNSYNCED` (Important 1);
    test_deleted_is_idempotent rewritten with org_id="org_1" (Important 3); dead logger import
    removed from auth.py; database.py logs constraint_name instead of str(e); the nonexistent
    --limit-max-request-size flag removed from webhook.py's comment; CLAUDE.md and the spec
    both modified.
  NOT DONE, carried into the resume: the membership-deleted org guard is still the broad
    `not in (None, user.org_id)` form (Important 2 — the supplier-orphaning one);
    USER_PAYLOAD still lists the primary address first; no overflow guard in
    clerk_timestamp_to_datetime; supplier_unlinked_on_offboarding still unconditional.
  Also handed to the resume as a judgment call: _UNSYNCED kept its private underscore name
    while now being imported across two module boundaries — a naming contradiction to resolve.

=== FIX-WAVE RE-REVIEW ===
Verdict: all findings ADDRESSED, no new Critical/Important BEHAVIOURAL breakage. Two-agent seam
  checked clean (one UNSYNCED_EPOCH definition, no duplicate/shadowed tests, no test orphaned
  from its implementation, zero rename stragglers repo-wide). Guard proven strictly narrower by
  case analysis: (None,X) (X,X) (A,B) all unchanged; only (A,None) flipped return->proceed.

Ruling: I am making a DELIBERATE EXCEPTION to "there is no second fix wave", for one finding.
  The re-review found that the database.py IntegrityError fix applied my prescribed remedy
  EXACTLY and still did not achieve its goal. I verified this myself: line 66 is
  logger.exception(), which sets exc_info=True, and structlog's format_exc_info sits in the
  shared processor chain (app/core/logging.py:349) applied to both console and JSON configs. The
  rendered traceback's terminal line is the IntegrityError repr — the same string str(e) gave,
  carrying [SQL: ...] [parameters: {'email': ...}] — plus a chained psycopg UniqueViolation frame
  with `DETAIL: Key (email)=(...) already exists.` The email still reaches the logs on every
  User.email unique violation, now including via the new UNAUTHENTICATED webhook path.
  — Why this warrants the exception: the leak is pre-existing, but the diff added a comment
    asserting "This is also the only thing logged", which is FALSE and would stop the next
    reader from ever finding it. Shipping a comment that actively conceals a PII leak is worse
    than shipping the leak alone. The correction is one word.
  — Also folding in two things the same re-review surfaced, both small and both regressions
    introduced by the fix wave rather than pre-existing:
    (a) `constraint` now reaches the HTTP RESPONSE BODY on every 409 app-wide (the old getattr
        chain always evaluated None, so this is new client-visible behaviour nobody asked for).
        Reverting to log-only restores pre-branch behaviour.
    (b) the new CLAUDE.md ngrok row puts a 200-char sentence in a column headed "URL".
  — NOT folding in: the OperationalError/DBAPIError sibling branches that still log str(e).
    Same channel, but they fire on connection faults unrelated to the webhook path, and str(e)
    is the actual diagnostic there. Deferred to the user as a follow-up.
Final corrections: commits 127f27c, b49aace, 4fad6ec. 428/428 passing. Leak closure verified
  EMPIRICALLY with a control — the implementer drove get_db_session() with a realistic psycopg
  UniqueViolation-shaped IntegrityError, captured the rendered structlog JSON, confirmed no email,
  AND ran a control with logger.exception() on the identical exception showing it DOES leak,
  proving the harness can detect a real leak rather than merely reporting a pass.
Verified myself: comment now explains the deliberate divergence from the .exception() convention
  (so it survives future tidying), and constraint no longer reaches DatabaseConflictError's
  context, restoring the pre-branch 409 response shape.

=== WS4 COMPLETE — ready for hand-off ===
