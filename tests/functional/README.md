# DirectAI — Functional Tests

End-to-end tests that hit **live deployed endpoints**. They verify the full
request path: TLS → Ingress → API server → inference backends (and the web
frontend). These are NOT unit tests — they require a running environment.

## What's tested

| File | Endpoints | Coverage |
|---|---|---|
| `test_health.py` | `/healthz`, `/readyz`, `/metrics` | Liveness, readiness, Prometheus scrape |
| `test_auth.py` | `/v1/models`, `/v1/embeddings`, `/v1/chat/completions` | 401 enforcement, invalid keys, `X-Request-ID` |
| `test_models.py` | `GET /v1/models` | OpenAI list schema, expected models, alias expansion |
| `test_embeddings.py` | `POST /v1/embeddings` | Single + batch, 1024-dim, usage, aliases, errors |
| `test_chat.py` | `POST /v1/chat/completions` | Sync + streaming SSE, usage, aliases, `[DONE]` |
| `test_web.py` | `https://agilecloud.ai` | Landing page, public pages, dashboard auth, headers |

## Running locally

```bash
pip install httpx pytest

export DIRECTAI_FUNC_TEST_KEY="dai_sk_func_test_..."
export DIRECTAI_FUNC_TEST_BASE_URL="https://api.agilecloud.ai"   # default
export DIRECTAI_FUNC_TEST_WEB_URL="https://agilecloud.ai"        # default
export DIRECTAI_FUNC_TEST_DELAY="1.5"                             # rate-limit pacer (seconds)

pytest tests/functional/ -v --tb=short
```

Without `DIRECTAI_FUNC_TEST_KEY`, only unauthenticated tests (health, web)
will run — authenticated tests are skipped automatically.

## CI / CD integration

The functional tests run automatically in GitHub Actions via
`.github/workflows/functional-tests.yml`:

| Trigger | Scope | When |
|---|---|---|
| **build-api-server.yml** → deploy | `api` | After API server Helm upgrade |
| **build-web.yml** → deploy | `web` | After web frontend Helm upgrade |
| **Manual** (`workflow_dispatch`) | configurable | On-demand |
| **Nightly schedule** | `all` | 06:00 UTC daily |

### Required GitHub secret

Set `FUNC_TEST_API_KEY` on the **`platform`** environment in repo settings.
This is the bearer token for the test API key in the shared PostgreSQL
database. The key was created via `scripts/create-test-apikey.py`.

### Rate limiting

The live API server enforces 60 RPM. The `conftest.py` pacer sleeps
`DIRECTAI_FUNC_TEST_DELAY` seconds (default 1.5) between API calls to
stay under the limit. In CI this adds ~90 seconds to the full suite —
acceptable for a post-deploy gate.
