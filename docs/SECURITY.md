# ShivAI Security Policy & Safeguards

## 1. Secret Management & Zero-Leakage Guarantee

1. **No Plaintext Secrets in Code**: Secrets are never hardcoded. All keys are injected via environment variables.
2. **Automated Secret Redaction**: The `SecretRedactor` filter sits between logging/exceptions and all output streams:
   - Configured keys are exact-matched and replaced with `[REDACTED_SECRET]`.
   - Heuristic regular expressions match vendor patterns (`sk-...`, `AIza...`, `gsk_...`, Bearer tokens) and replace them with `[REDACTED_API_KEY]`.
3. **Safe Error Responses**: Raw tracebacks and downstream provider error payloads are scrubbed. The user receives standardized JSON errors containing only a high-level message and a unique `request_id`.

---

## 2. API Gateway Security

- **Authentication**: Caller identification via `X-API-Key` or `Authorization: Bearer <token>`.
- **Sliding Window Rate Limiter**: Enforces maximum requests per minute per IP, returning HTTP 429 with `Retry-After`.
- **Security Headers**: Injects:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Content-Security-Policy: default-src 'self'`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains`

---

## 3. Tool Sandboxing

- **AST Calculator**: Uses Python's `ast` parsing module to compute arithmetic expressions. `eval()` and `exec()` are strictly banned, preventing arbitrary code execution.
- **Permission Gates**: Every tool defines required permissions. Tools can only be executed if the caller or active agent explicitly grants the required permission.
