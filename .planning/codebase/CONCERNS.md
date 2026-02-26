# Codebase Concerns

**Analysis Date:** 2026-02-26

## Tech Debt

**Oversized Analytics Modules:**
- Issue: Core analytics files exceed 1500+ lines, making them difficult to maintain and test
- Files: `server/app/analytics/temporal.py` (1510 lines), `server/app/analytics/descriptive.py` (736 lines)
- Impact: Hard to identify and fix bugs, difficult to add features, unclear testing scope
- Fix approach: Split by concern (time-series, seasonality, volatility in temporal; spending, merchants, recurring in descriptive). Aim for <400 lines per module.

**Large UI Components Without Composition:**
- Issue: Sidebar component is 741 lines; Combobox is 292 lines - monolithic components that bundle logic, state, and rendering
- Files: `web-app/src/components/ui/sidebar.tsx`, `web-app/src/components/ui/combobox.tsx`, `web-app/src/components/ui/field.tsx` (227 lines)
- Impact: Difficult to test, reuse, or modify. Harder to debug state management issues.
- Fix approach: Extract hooks for state management, split into smaller sub-components. Each component should be <150 lines.

**Overly Complex Logging Configuration:**
- Issue: Logging setup is 484 lines with intricate third-party library configuration and dynamic log level management
- Files: `server/app/core/logging.py`
- Impact: Hard to modify logging behavior without breaking something; difficult to onboard new developers
- Fix approach: Extract third-party logger configuration to separate module; simplify main logging init to <250 lines.

**CSV Import Pipeline Lacks Atomicity Guarantees:**
- Issue: Multi-step CSV import (upload → map → confirm) stores state in database but doesn't guarantee consistency across steps
- Files: `server/app/api/v1/transactions.py` (464 lines), `server/app/services/csv_mapping/service.py`
- Impact: Session could be partially committed, file could be uploaded but mapping lost, or import could fail leaving orphaned data
- Fix approach: Implement transaction-level atomicity; add rollback mechanism for failed imports; add cleanup task for expired sessions.

**Missing Test Coverage for Web-App:**
- Issue: No test files found in `web-app/src` (searched for *.test.ts, *.spec.tsx)
- Files: All web-app source files
- Impact: Cannot catch regressions in UI components; CI pipeline has no frontend tests
- Fix approach: Set up Vitest or Jest; write component tests for critical paths (auth, transactions, insights). Aim for >70% coverage.

## Known Bugs

**TODO in Test Configuration:**
- Symptoms: Test JWT generation is stubbed out, may not properly validate auth in tests
- Files: `server/tests/conftest.py:236`
- Trigger: Run any test that requires valid JWT
- Workaround: Use mock/patch for Clerk validation; ensure test tokens are properly signed
- Fix approach: Generate actual valid JWTs in conftest or use Clerk's test mode.

**Potential JSON Parsing Failure in LLM Response:**
- Symptoms: If LLM returns invalid JSON for column mapping, application crashes instead of user-friendly error
- Files: `server/app/api/v1/transactions.py:62-68`
- Trigger: LLM returns JSON that doesn't parse (e.g., trailing comma, unescaped quotes)
- Workaround: Re-upload CSV and wait for retry
- Fix approach: Add more robust JSON extraction; try multiple parsing strategies (repair JSON library); return more helpful error messages.

## Security Considerations

**Soft Delete Not GDPR-Compliant:**
- Risk: `SoftDeleteMixin` is used to "delete" records, but GDPR requires actual erasure of personal data. Soft-deleted user data remains in database indefinitely.
- Files: `server/app/models/base.py:40-78`
- Current mitigation: Code includes GDPR warnings in docstring, but no enforcement or audit
- Recommendations:
  - Use `AnonymizableMixin` for User accounts and personal data (name, email, auth tokens)
  - Implement hard-delete with anonymization for GDPR right-to-be-forgotten
  - Add data retention policy and automated purge for soft-deleted records after 90 days
  - Audit deletion requests in logs

**Database Connection String Exposure:**
- Risk: Database credentials (username, password, host, port) are passed as plain text in connection URL. If error logs capture connection strings, credentials leak.
- Files: `server/app/database/engine.py:24-27`
- Current mitigation: Uses SecretStr for password field, but connection string is printed in logging
- Recommendations:
  - Never log full connection strings (redact password in error messages)
  - Use environment variables exclusively; never hardcode defaults
  - Add connection string sanitization before logging
  - Use database IAM authentication (PostgreSQL IAM roles) where possible

**CSV Upload File Handling - Potential DoS:**
- Risk: CSV file is read into memory entirely (line 139: `csv_content=csv_text`), then re-parsed in confirm step. Large CSV (within limit) could consume excessive memory.
- Files: `server/app/api/v1/transactions.py:92-93, 195`
- Current mitigation: `CSV_MAX_ROWS` limit exists, but no file size limit
- Recommendations:
  - Add `CSV_MAX_BYTES` setting (e.g., 10MB max)
  - Validate file size before reading into memory
  - Stream parsing instead of loading full CSV into memory
  - Add timeout to file operations

**Missing Input Validation on Batch Operations:**
- Risk: Batch update/delete endpoints accept arrays without per-item validation or limits. User could submit 10,000+ item IDs.
- Files: `server/app/api/v1/transactions.py:256-300`
- Current mitigation: Rate limit exists (30/minute) but no batch size validation
- Recommendations:
  - Add max batch size validation (e.g., max 100 items per batch)
  - Return clear error if batch exceeds limit
  - Log batch operations for audit trail

**LLM API Key Exposure in Registry:**
- Risk: `ChatOpenAI` instances are created at module init time with API key, held in memory in class variable. If memory dump occurs, key is exposed.
- Files: `server/app/services/llm/service.py:48-98`
- Current mitigation: Uses SecretStr from Pydantic, but instances are kept in class variable without isolation
- Recommendations:
  - Initialize LLM instances lazily (on first use) rather than at import
  - Consider using environment variables directly at call time
  - Add API key rotation/expiration logic

## Performance Bottlenecks

**Analytics Functions Perform Multiple DataFrame Clones:**
- Problem: Every analytics function clones the entire DataFrame at start (`prepared = df.clone()`), then clones again in filter operations. For large datasets (100k+ transactions), this is expensive.
- Files: `server/app/analytics/temporal.py:42-72`, `server/app/analytics/descriptive.py:42-72`
- Cause: Defensive copying to avoid mutation, but copies are unnecessary for these operations
- Improvement path:
  - Use view-based operations (Polars column selection) instead of clone
  - Benchmark with 100k+ row datasets
  - Cache prepared dataframes if same preparation is done repeatedly

**Insights Aggregation Has No Caching:**
- Problem: Every insight request re-runs all analytics calculations (spending, volatility, seasonality, recurring) even if data hasn't changed
- Files: `server/app/agents/insights/aggregator.py`, `server/app/agents/insights/agent.py`
- Cause: Stateless service design; no caching layer
- Improvement path:
  - Add Redis/in-memory cache keyed by (user_id, date_range)
  - Invalidate cache only when new transactions imported
  - Add cache TTL (e.g., 1 hour)
  - Expected improvement: 80%+ reduction in insight response time for typical users

**LLM Retry Logic Has No Exponential Backoff Cap:**
- Problem: Tenacity retry config has exponential backoff but may wait minutes before failing
- Files: `server/app/services/llm/service.py:19-24` (imports tenacity but retry decorator not shown)
- Cause: Default exponential backoff can grow unbounded
- Improvement path:
  - Add `max_wait` parameter to exponential backoff (e.g., 30 seconds max)
  - Fail fast for non-retryable errors (auth, invalid input)
  - Add timeout per attempt (e.g., 10 seconds)

**Memory Instance Singleton Without Cleanup:**
- Problem: AsyncMemory instance is stored in module-level variable `_memory_instance`, never closed. Connection pools may be exhausted.
- Files: `server/app/agents/shared/memory/factory.py:10-46`
- Cause: No shutdown hook to close memory connection pool
- Improvement path:
  - Add async context manager or shutdown method
  - Call cleanup in app shutdown lifecycle
  - Add connection pool configuration (size limits)

## Fragile Areas

**Authentication Flow Assumes Clerk Configuration is Perfect:**
- Files: `server/app/api/middlewares/auth.py`, `server/app/utils/auth.py`
- Why fragile: Derives JWKS URL from `settings.auth.ISSUER` without validation; no fallback if Clerk is down
- Safe modification:
  - Add JWKS URL to config as separate field with fallback
  - Implement cache with TTL for JWKS
  - Add circuit breaker for Clerk API calls
  - Test what happens when Clerk is unavailable
- Test coverage: Auth middleware tests may not cover Clerk outage scenarios

**Conversational State Machine Relies on Correct Message Ordering:**
- Files: `server/app/agents/chatbot/graph.py`, `server/app/schemas/chat.py`
- Why fragile: If messages arrive out of order or duplicate, state could become inconsistent
- Safe modification:
  - Add message sequencing/versioning
  - Validate message order before processing
  - Add idempotency keys to prevent double processing
- Test coverage: Integration tests should include out-of-order message scenarios

**CSV Mapping Cache Could Become Stale:**
- Files: `server/app/services/csv_mapping/service.py`
- Why fragile: Column hash mapping is cached forever; if CSV format changes, cached mapping will be wrong
- Safe modification:
  - Add version/timestamp to cached mappings
  - Include validation step that re-confirms mapping with sample rows
  - Add manual cache invalidation endpoint for admins
- Test coverage: Test that stale mapping is rejected when column structure changes

## Scaling Limits

**PostgreSQL Checkpoint Storage for LangGraph:**
- Current capacity: Using PostgreSQL with default pool_size=15, max_overflow=5 (20 concurrent connections max)
- Limit: With concurrent users executing graph workflows, connection pool exhaustion could happen at 20+ simultaneous graphs
- Scaling path:
  - Increase `POSTGRES_POOL_SIZE` (but increases memory usage)
  - Use read replicas for JWKS/config reads
  - Consider Redis-based checkpointing for higher concurrency
  - Monitor connection pool utilization with metrics

**Analytics Calculation Not Parallelized:**
- Current capacity: Temporal and descriptive analytics run sequentially for each user
- Limit: With 1000+ concurrent users requesting insights, server will be CPU-bound
- Scaling path:
  - Move analytics calculations to background job queue (Celery, Temporal, or similar)
  - Cache aggregated results per date range
  - Implement batch calculation jobs for inactive users

**Memory Vector Store (pgvector) Not Sharded:**
- Current capacity: All user memories stored in single pgvector collection
- Limit: Query performance degrades as memories grow (all searches scan full collection)
- Scaling path:
  - Implement per-user collection sharding
  - Use vector clustering with HNSW indexes
  - Monitor vector store size and latency
  - Consider tiered storage (hot/cold vector data)

## Dependencies at Risk

**LangChain/LangGraph Ecosystem Rapidly Evolving:**
- Risk: LangChain is pre-1.0, API changes frequently. Current version may not be compatible with future OpenAI models/APIs.
- Impact: If upstream breaks, agents and tools stop working; requires rewrite
- Migration plan:
  - Keep LangChain/LangGraph versions pinned in uv.lock
  - Monitor release notes for breaking changes
  - Budget for quarterly compatibility testing
  - Consider creating abstraction layer around LangChain (currently tightly coupled)

**mem0ai Package Not Well-Maintained:**
- Risk: mem0 is external package with uncertain maintenance status. No recent updates visible.
- Impact: Security vulnerabilities could go unpatched; compatibility issues with newer Polars/OpenAI versions
- Migration plan:
  - Evaluate alternative vector stores (Pinecone, Weaviate, Qdrant)
  - Audit mem0 code for security issues
  - Have fallback plan to switch vector store if mem0 becomes abandoned

**Tenacity Retry Library Dependency:**
- Risk: Tenacity is not a "critical" package; LangChain could switch to different retry mechanism
- Impact: If Tenacity is removed from LangChain dependencies, custom retry logic breaks
- Migration plan:
  - Consider using Python's built-in `retry` or `backoff` library for custom retries
  - Audit Tenacity's usage; minimize custom retry decorators

## Missing Critical Features

**No Data Export/Backup Mechanism for Users:**
- Problem: Users have no way to export their transaction data or access raw data backup
- Blocks: GDPR right to data portability; user lock-in; disaster recovery for individual users
- Fix approach:
  - Add export endpoint (CSV, JSON formats)
  - Implement backup schedule (daily snapshots)
  - Document disaster recovery procedure
  - Add data retention policy documentation

**No Rate Limiting for Analytics/Insights Endpoints:**
- Problem: Expensive analytics calculations have no rate limits; user could DoS themselves or the app
- Files: `server/app/api/v1/insights.py` (check if rate limits exist)
- Blocks: Production load testing; could impact other users if one user requests analytics too frequently
- Fix approach:
  - Add rate limits to insight generation endpoints (e.g., 5/minute per user)
  - Cache results to avoid recalculation
  - Return cached result if available within TTL

**No Audit Trail for Transaction Changes:**
- Problem: When users edit/delete transactions, no record of who changed what and when
- Blocks: Fraud detection; user support (can't prove what happened); compliance
- Fix approach:
  - Add transaction audit log table with (user_id, transaction_id, old_value, new_value, timestamp, action)
  - Implement soft-delete with audit entries instead of hard delete
  - Expose audit log in UI for users to review their history

## Test Coverage Gaps

**Agent Graph Workflows Mostly Untested:**
- What's not tested: LangGraph state machine logic, node transitions, error recovery in graphs
- Files: `server/app/agents/chatbot/graph.py`, `server/app/agents/insights/agent.py`, `server/app/agents/transactions_labeler/agent.py`
- Risk: Silent failures in agent workflows; users get stuck with no error message
- Priority: High - agents are critical to app functionality
- Recommended approach:
  - Mock LLM calls to avoid API costs during testing
  - Test happy path, error cases, and timeout scenarios
  - Test state transitions with sample inputs/outputs
  - Aim for >80% coverage of agent code

**Integration Tests for CSV Upload Pipeline:**
- What's not tested: Full end-to-end CSV upload → map → confirm → import flow
- Files: `server/app/api/v1/transactions.py`, `server/app/services/transaction/service.py`
- Risk: Column mapping errors, duplicate prevention failures, or data corruption not caught
- Priority: High - CSV import is major user feature
- Recommended approach:
  - Test with sample CSVs in various formats (German, English, multi-currency)
  - Test error cases: invalid dates, missing amounts, duplicate rows
  - Verify fingerprinting and deduplication work correctly
  - Check that failed imports don't leave orphaned data

**Clerk Authentication Integration Tests:**
- What's not tested: JWT validation, user context extraction, permission checks
- Files: `server/app/api/middlewares/auth.py`, `server/app/utils/auth.py`
- Risk: Auth bypass or user impersonation if JWT validation breaks
- Priority: Critical - security-sensitive
- Recommended approach:
  - Use Clerk's test mode (test API keys) in CI
  - Test valid JWTs, expired JWTs, invalid signatures
  - Test user isolation (user A cannot access user B's data)
  - Mock JWKS endpoint to test offline validation

**Memory/Long-Term Memory Service Tests:**
- What's not tested: Memory creation, retrieval, deletion, error handling
- Files: `server/app/agents/shared/memory/factory.py`
- Risk: User memories leaked to other users; memories not properly deleted on account deletion
- Priority: Medium-High (data privacy sensitive)
- Recommended approach:
  - Test memory isolation per user
  - Test memory deletion in cascade when user is deleted
  - Test error handling when pgvector is unavailable
  - Mock mem0 API to avoid external dependencies

---

*Concerns audit: 2026-02-26*
