# Urja Meter Ops API

A clean REST API in front of the Urja Meter Ops portal (a legacy SvelteKit
app with no public API of its own). See [PROTOCOL.md](PROTOCOL.md) for how
the portal actually works under the hood.

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # then edit if you want different credentials
.venv/bin/uvicorn app.main:app --reload --port 8000
```

### Configuration (`.env`)

| Variable | Meaning |
|---|---|
| `PORTAL_BASE_URL` | Base URL of the Urja Meter Ops portal we're wrapping |
| `PORTAL_USERNAME` / `PORTAL_PASSWORD` | Login credentials for that portal — used internally by `PortalClient`, never exposed to callers of this API |
| `CACHE_TTL_SECONDS` | How long the in-memory meter/DT/consumption caches are trusted before a refresh is triggered (default 300s) |
| `CACHE_ENABLED` | Set to `false` to bypass caching entirely and hit the portal fresh on every request (useful for testing) |
| `AUTH_ENABLED` | Set to `false` to switch this API's own JWT auth off entirely — every route becomes open and the four settings below are ignored. Handy for poking at endpoints with plain `curl`; don't ship it |
| `API_USERNAME` / `API_PASSWORD` | Credentials for **this API's own** `POST /auth/login` — unrelated to the portal creds above |
| `JWT_SECRET_KEY` | Signing secret for the JWTs this API issues. The default is a placeholder — change it for anything beyond local dev |
| `JWT_EXPIRE_MINUTES` | How long an issued token stays valid (default 60) |

`.env.example` ships with working defaults (including the assignment's
demo portal credentials), so `cp .env.example .env` alone is enough to run
everything below as-is.

Interactive docs (Swagger UI): `http://localhost:8000/docs`

`openapi.json` in the repo root is a static export of this API's OpenAPI
3.1 schema (not the portal's — ours), generated directly from the FastAPI
app (`app.openapi()`) rather than hand-authored.

## Auth

Every route except `/health` and `/auth/login` requires a JWT bearer token.
Get one first:

```bash
curl -X POST http://localhost:8000/auth/login \
  -H 'content-type: application/json' \
  -d '{"username":"admin","password":"flock-energy-2026"}'
# -> {"access_token":"eyJhbGciOi...", "token_type":"bearer"}

TOKEN=eyJhbGciOi...   # paste the token above
```

Every example below assumes `$TOKEN` is set like this. To skip auth altogether
during local exploration, set `AUTH_ENABLED=false` in `.env` and drop the
`Authorization` header from every command below.

## Endpoints

### `GET /health`

No auth required.

```bash
curl http://localhost:8000/health
```

### `POST /auth/login`

```bash
curl -X POST http://localhost:8000/auth/login \
  -H 'content-type: application/json' \
  -d '{"username":"admin","password":"flock-energy-2026"}'
```

### `GET /meters` — list, search, filter

Params: `search`, `meter_id`, `serial_no`, `make`, `phase_type`, `status`,
`dt_code`, `page`, `page_size` (up to 1000).

```bash
# first page, defaults
curl http://localhost:8000/meters -H "Authorization: Bearer $TOKEN"

# free-text search (matches meter_id or serial_no)
curl "http://localhost:8000/meters?search=SE33962" -H "Authorization: Bearer $TOKEN"

# exact filters, combinable
curl "http://localhost:8000/meters?make=Genus&status=Faulty" -H "Authorization: Bearer $TOKEN"

# all meters on one DT
curl "http://localhost:8000/meters?dt_code=DT-011" -H "Authorization: Bearer $TOKEN"

# entire dataset in one call
curl "http://localhost:8000/meters?page_size=1000" -H "Authorization: Bearer $TOKEN"
```

### `GET /meters/{meter_id}` — single meter detail + full network hierarchy

Includes fields not in the list view (`installation_type`) and the complete
Zone → Circle → Division → Subdivision → Substation → Feeder → DT chain for
this meter (see PROTOCOL.md for how this is reverse-engineered from the
portal's internal SvelteKit data format).

```bash
curl http://localhost:8000/meters/J100000 -H "Authorization: Bearer $TOKEN"

# unknown meter -> clean 404 (the portal itself returns 200 with an embedded
# error for this case - we translate it)
curl -i http://localhost:8000/meters/DOES-NOT-EXIST -H "Authorization: Bearer $TOKEN"
```

### `GET /network/dts` — DT-level network position

Params: `search`, `dt_code`, `name`, `feeder_code`, `capacity_kva`, `page`,
`page_size`.

```bash
curl http://localhost:8000/network/dts -H "Authorization: Bearer $TOKEN"

curl "http://localhost:8000/network/dts?search=Malviya" -H "Authorization: Bearer $TOKEN"

curl "http://localhost:8000/network/dts?feeder_code=F-003" -H "Authorization: Bearer $TOKEN"

curl "http://localhost:8000/network/dts?capacity_kva=63" -H "Authorization: Bearer $TOKEN"

curl "http://localhost:8000/network/dts?page_size=1000" -H "Authorization: Bearer $TOKEN"
```

### `GET /meters/{meter_id}/consumption` — recent usage

Half-hourly readings, rolling ~7-day window (that's all the portal itself
exposes — see PROTOCOL.md). Params: `start`, `end` (ISO 8601, filters the
window locally), `page`, `page_size`.

```bash
curl http://localhost:8000/meters/J100000/consumption -H "Authorization: Bearer $TOKEN"

# narrow to one day
curl "http://localhost:8000/meters/J100000/consumption?start=2026-06-25T00:00:00&end=2026-06-25T23:59:59" \
  -H "Authorization: Bearer $TOKEN"

# unknown meter -> clean 404, not a leaked portal error
curl -i "http://localhost:8000/meters/DOES-NOT-EXIST/consumption" -H "Authorization: Bearer $TOKEN"
```

### `POST /admin/cache/clear`

Forces an immediate refresh on next read instead of waiting out the cache
TTL.

```bash
curl -X POST http://localhost:8000/admin/cache/clear -H "Authorization: Bearer $TOKEN"
```

## Notes

### Assumptions

- The portal's `search`/`q` semantics (substring match against meter number
  or serial number) were reverse-engineered by testing, not documented
  anywhere — we mirror that same behavior in our own `search` param.
- The in-memory full-dataset caching approach assumes the data stays at
  roughly today's scale (403 meters, 40 DTs). It's an assumption about the
  *portal's* scale, not something we control — see "what we'd improve"
  below for where this would need to change if that assumption stopped
  holding.
- "Recent consumption" is assumed to mean whatever fixed window the portal
  itself exposes (confirmed: a rolling 7-day window, no date-range control
  anywhere in the UI) rather than something wider we could coax out of it.
- Assumed the raw cumulative `kwh`/`kvah` register readings are more honest
  to pass through as-is than to silently convert them into per-interval
  deltas — a real design choice, not free information from the portal (see
  PROTOCOL.md).
- Assumed adding our own JWT auth layer was worth doing even though the
  assignment didn't require it — once `POST /admin/cache/clear` existed, an
  unauthenticated destructive-ish action felt like a real gap worth closing.
- Confirmed (not just assumed) that no standalone `/portal/feeders`,
  `/portal/substations`, etc. endpoints exist — checked directly by
  guessing at the portal's own naming convention.

### Design decisions & trade-offs

- **Full in-memory caching instead of proxying the portal's pagination
  1:1** — trades a few minutes of staleness for arbitrary page sizes,
  cross-field filtering the portal can't do, and far fewer round trips to a
  legacy system we don't control.
- **Generic, data-driven filtering** — loops over a tuple/dict of field
  names instead of one `if` per attribute, so adding a new filterable field
  is a one-line change.
- **A separate JWT layer for our own API**, fully decoupled from the
  portal's own better-auth session cookie — two independent trust
  boundaries. One shared credential pair for now, not per-client, to keep
  scope reasonable.
- **Hand-written devalue decoder** for the portal's SvelteKit `__data.json`
  format (PROTOCOL.md), rather than pulling in a JS runtime or a
  devalue-compatible library — kept the service pure-Python once the format
  was actually understood.
- **Portal quirks absorbed at the boundary, not leaked through**: the
  "200-with-embedded-error" response for an unknown meter becomes a real
  `404`; string-typed `"kwh": "48438.74"` becomes an actual number;
  `DD/MM/YYYY HH:MM` becomes a real ISO datetime. A consumer of this API
  should never need to know the portal's idiosyncrasies exist.
- **Cache clear + a disable switch exposed explicitly**, not just an
  internal TTL — useful for testing now, and a reasonable ops lever later.

### What we intentionally skipped

- **Standalone list endpoints for Substation/Feeder/Division/Circle/Zone.**
  The full hierarchy is available, but only inline per-meter via
  `GET /meters/{id}` — there's no `/network/substations` the way
  `/network/dts` exists for DTs. A deliberate scope cut given the time
  budget, not an oversight.
- **Derived per-interval consumption.** We expose the portal's raw
  cumulative register readings only, not a computed kWh-per-slot delta.
- **Automated tests.** `tests/` is still empty. Deprioritized on purpose —
  per the assignment's own stated evaluation order (problem-solving,
  judgment, learning, communication, and code quality all rank above
  architecture/testing/speed), the time budget went toward investigation
  depth and endpoint coverage instead.
- **A modern web client** (optional extension) — not attempted.
- **Refresh tokens / per-client scopes** for our own API's auth — one
  shared credential pair only.
- **Persisted or shared cache** (e.g. Redis) — in-memory, single-process
  only, which is fine for how this is meant to run today.
- A few PROTOCOL.md loose ends never chased down: the bad-login response
  shape, whether `/portal/dts` accepts a search param, and whether a bulk
  export path exists beyond what we're already using.

### What we'd improve with more time

- Standalone hierarchy-level listing endpoints, and ideally a proper nested
  tree endpoint (DT → Feeder → Substation → ... → Zone) instead of only the
  flat per-meter view.
- A computed/derived consumption view (kWh per interval) alongside the raw
  register passthrough.
- Real tests: the filtering/pagination logic and the devalue decoder are
  both easily unit-testable in isolation (no portal needed), plus a few
  integration tests against a mocked portal for the auth/caching behavior.
- Structured logging and basic observability — right now there's nothing
  beyond uvicorn's default access logs.
- Retry/backoff for transient portal network errors, beyond the
  session-expiry-specific retry that already exists.
- Nail down the remaining PROTOCOL.md open questions.

## Reflection

See [REFLECTION.md](REFLECTION.md) — assumptions, the hardest part and how
I got unstuck, what I'd improve with another day, a mistake I made, and
self-critique.

## More documentation

- [PROTOCOL.md](PROTOCOL.md) — how the portal actually works (auth, data
  endpoints, quirks, open questions)
- [REFLECTION.md](REFLECTION.md) — the reflection questions
- `openapi.json` — this API's OpenAPI 3.1 schema
