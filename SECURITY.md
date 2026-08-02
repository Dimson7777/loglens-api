# LogLens API Security Plan

## 1. Authentication and Authorization

Authentication:
- JWT bearer tokens with expiration.
- Access token signed with strong secret and configurable algorithm.
- Invalid credential responses are intentionally generic to reduce account enumeration risk.

Authorization:
- Role-based controls:
  - developer: create/read logs, trigger analysis
  - admin: all developer permissions + delete logs, manage users, change group status

Token handling:
- Short-lived access tokens and longer-lived refresh tokens.
- Access and refresh tokens may use separate signing secrets.
- Refresh tokens rotate on use, and token families are revoked on reuse detection.

## 2. Password Security

- Password hashing via Argon2id or bcrypt with strong work factor.
- Current implementation uses Argon2.
- Never store plaintext passwords.
- Enforce password complexity and minimum length.
- Uniform login error messaging to avoid account enumeration.

## 3. Input Validation and Output Safety

- Pydantic v2 strict models for all request payloads.
- Enum constraints for environment, levels, statuses.
- Bounded string lengths and list sizes.
- Return safe, standardized error messages without stack traces.

## 4. Injection and Data Access Protection

- SQLAlchemy ORM/Core parameterized queries only.
- No direct string concatenation for SQL.
- Controlled sort/filter fields through allow-list validation.

## 5. Transport and Deployment Security

- Assume TLS termination at reverse proxy in production.
- CORS allow-list configured via environment variables.
- Secure headers can be added at gateway or middleware layer.

## 6. Rate Limiting and Abuse Protection

- Redis-backed rate limiting for auth and ingestion routes.
- Endpoint-specific limits and bursts.
- Block oversize payloads via request-size middleware.

Current implementation status:
- Baseline login rate limiting is implemented in Redis keyed by IP and email.
- Redis outages are treated as fail-open for login throttling so authentication stays available.

## 7. Secret Management

- No hardcoded secrets.
- Environment-driven configuration with validation on startup.
- .env.example includes placeholders only.
- AI API key optional and never logged.

Additional production guidance:
- Rotate JWT secrets regularly.
- Inject JWT and bootstrap credentials from a secret manager such as AWS Secrets Manager, Azure Key Vault,
  or HashiCorp Vault.
- Use environment or secret manager injection for ADMIN_BOOTSTRAP_PASSWORD and run seeding once.
- If refresh tokens are later moved to HttpOnly cookies, add CSRF protections before enabling the cookie flow.

## 8. Logging and Privacy

- Structured JSON logs with correlation IDs.
- Avoid logging secrets and sensitive fields.
- Stack traces stored from client logs by design; add retention policy and access controls.

## 9. Dependency and Supply Chain Practices

- Pin dependency ranges in pyproject.
- CI runs lint/type/tests and Docker build.
- pip-audit runs in CI security workflow to surface new CVEs.

### Phase 5 pip-audit Status (2026-08-02)

Fixable vulnerabilities: **0** — all direct dependencies are at patched versions.

Remaining unfixable transitive vulnerabilities (2 packages, 8 CVEs):

**`ecdsa 0.19.2`** — PYSEC-2026-1325
- Pulled in by `python-jose` (JWT encoding/decoding).
- `ecdsa 0.19.2` is the latest release; no upstream fix version exists on PyPI.
- Mitigation: `python-jose` uses `python-cryptography` as the primary signing backend; the `ecdsa` path is only used for EC key types not exercised in this project.

**`starlette 0.52.1`** — PYSEC-2026-161, PYSEC-2026-248, PYSEC-2026-249, PYSEC-2026-2280, PYSEC-2026-2281 (+ 2 duplicates)
- Pulled in by `prometheus-fastapi-instrumentator 7.1.0`, which pins `starlette<1.0.0`.
- Fix versions exist (starlette ≥ 1.0.1 through 1.3.1), but installing them breaks the instrumentator's declared constraint.
- Resolution path: upgrade `prometheus-fastapi-instrumentator` to a release that supports starlette 1.x, then upgrade starlette.
- No compatible upstream release is available as of this audit date.

## 10. Incident Readiness

- Health and readiness endpoints for operational checks.
- Metrics for auth failures, rate-limit hits, and task failures.
- Clear failure states for Celery jobs with retry tracking.

## 11. Phase 4 Addendum

Background-job security:
- Job status and analysis endpoints require authenticated developer/admin access.
- Job payloads are server-generated; clients only receive job metadata and progress.
- Idempotency and scope-locking reduce duplicate background execution risk.

AI integration controls:
- Default provider is `mock` for local/test environments.
- OpenAI-compatible provider requires explicit API key configuration.
- Provider output is validated against structured schema before persistence.
- Provider failures are mapped to failed analysis state without exposing sensitive internals.

Operational hardening notes:
- Celery container currently logs a root-user warning; production deployment should run worker with non-root UID.
- Redis should be network-restricted and authenticated in non-local environments.
