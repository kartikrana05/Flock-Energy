# API reference — every endpoint, as curl

Copy-pasteable `curl` for all seven endpoints of the Urja Meter Ops API. For what the
service is and how it's built, see [README.md](README.md); for how the underlying portal
works, see [PROTOCOL.md](PROTOCOL.md).

All examples assume the service is running on `http://localhost:8000`:

```bash
./run.sh            # or: .venv/bin/uvicorn app.main:app --reload --port 8000
```

## Contents

| Endpoint | Auth | What it does |
|---|---|---|
| [`GET /health`](#get-health) | no | liveness check |
| [`POST /auth/login`](#post-authlogin) | no | exchange credentials for a JWT |
| [`GET /meters`](#get-meters) | yes | list, search and filter meters |
| [`GET /meters/{meter_id}`](#get-metersmeter_id) | yes | one meter, plus its full network hierarchy |
| [`GET /meters/{meter_id}/consumption`](#get-metersmeter_idconsumption) | yes | half-hourly readings, rolling 7-day window |
| [`GET /network/dts`](#get-networkdts) | yes | distribution transformers |
| [`POST /admin/cache/clear`](#post-admincacheclear) | yes | force a refresh from the portal |

Interactive docs: <http://localhost:8000/docs>

---

## Getting a token

Every route except `/health` and `/auth/login` needs a bearer token. Grab one and keep it
in a shell variable — every example below uses `$TOKEN`.

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H 'content-type: application/json' \
  -d '{"username":"admin","password":"flock-energy-2026"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

echo "$TOKEN"
```

Tokens expire after `JWT_EXPIRE_MINUTES` (default 60). When they do, every call starts
returning `401 invalid or expired token` — just run the command above again.

> **Skipping auth entirely.** Set `AUTH_ENABLED=false` in `.env` and restart. Every route
> becomes open and you can drop the `-H "Authorization: Bearer $TOKEN"` from every command
> on this page. Local exploration only.

---

## `GET /health`

No auth. Returns static liveness — it does **not** check whether the portal is reachable.

```bash
curl http://localhost:8000/health
```

```json
{"status":"ok"}
```

---

## `POST /auth/login`

Exchanges the API's own credentials (`API_USERNAME` / `API_PASSWORD` from `.env`) for a
JWT. Unrelated to the portal's credentials, which the service holds internally and never
exposes.

```bash
curl -X POST http://localhost:8000/auth/login \
  -H 'content-type: application/json' \
  -d '{"username":"admin","password":"flock-energy-2026"}'
```

```json
{"access_token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...","token_type":"bearer"}
```

Wrong credentials give a clean `401`:

```bash
curl -i -X POST http://localhost:8000/auth/login \
  -H 'content-type: application/json' \
  -d '{"username":"admin","password":"wrong"}'
```

```json
{"detail":"invalid credentials"}
```

---

## `GET /meters`

List, search and filter meters. Served from an in-memory cache of the full dataset, so
filters combine freely and page sizes go well beyond the portal's own hard cap of 20.

| Param | Type | Default | Notes |
|---|---|---|---|
| `search` | string | — | case-insensitive substring over `meter_id` **or** `serial_no` |
| `meter_id` | string | — | exact, case-insensitive |
| `serial_no` | string | — | exact, case-insensitive |
| `make` | string | — | `HPL`, `L&T`, `Genus`, `Allied`, `Secure` |
| `phase_type` | string | — | `single` or `three` |
| `status` | string | — | `Installed`, `Faulty`, `Decommissioned` |
| `dt_code` | string | — | e.g. `DT-001` |
| `page` | int | `1` | min 1 |
| `page_size` | int | `20` | 1–1000 |

**Defaults — first page of 20**

```bash
curl "http://localhost:8000/meters" -H "Authorization: Bearer $TOKEN"
```

```json
{
  "data": [
    {
      "meter_id": "J100000",
      "serial_no": "SE33962",
      "make": "HPL",
      "phase_type": "single",
      "status": "Decommissioned",
      "dt_code": "DT-001"
    }
  ],
  "total": 403,
  "page": 1,
  "page_size": 20
}
```

**Free-text search** — matches meter number or serial number

```bash
curl "http://localhost:8000/meters?search=SE33962" -H "Authorization: Bearer $TOKEN"
curl "http://localhost:8000/meters?search=J1000"   -H "Authorization: Bearer $TOKEN"
```

**Exact filters**

```bash
curl "http://localhost:8000/meters?make=Genus"        -H "Authorization: Bearer $TOKEN"
curl "http://localhost:8000/meters?status=Faulty"     -H "Authorization: Bearer $TOKEN"
curl "http://localhost:8000/meters?phase_type=three"  -H "Authorization: Bearer $TOKEN"
curl "http://localhost:8000/meters?serial_no=SE33962" -H "Authorization: Bearer $TOKEN"
```

**Combined filters** — the portal itself cannot express this query

```bash
curl "http://localhost:8000/meters?make=Genus&status=Faulty&phase_type=single" \
  -H "Authorization: Bearer $TOKEN"
```

**Every meter on one transformer**

```bash
curl "http://localhost:8000/meters?dt_code=DT-007" -H "Authorization: Bearer $TOKEN"
```

**Pagination, and the whole dataset in one call**

```bash
curl "http://localhost:8000/meters?page=3&page_size=50" -H "Authorization: Bearer $TOKEN"
curl "http://localhost:8000/meters?page_size=1000"      -H "Authorization: Bearer $TOKEN"
```

**Just the IDs, via jq**

```bash
curl -s "http://localhost:8000/meters?page_size=1000" -H "Authorization: Bearer $TOKEN" \
  | jq -r '.data[].meter_id'
```

**Count by make**

```bash
curl -s "http://localhost:8000/meters?page_size=1000" -H "Authorization: Bearer $TOKEN" \
  | jq -r '.data | group_by(.make)[] | "\(.[0].make): \(length)"'
```

---

## `GET /meters/{meter_id}`

One meter, including two things the list view doesn't carry: `installation_type`, and the
complete Zone → Circle → Division → Subdivision → Substation → Feeder → DT chain. Each
hierarchy level is split into a separate `name` and `code`.

```bash
curl "http://localhost:8000/meters/J100000" -H "Authorization: Bearer $TOKEN"
```

```json
{
  "meter_id": "J100000",
  "serial_no": "SE33962",
  "make": "HPL",
  "phase_type": "single",
  "status": "Decommissioned",
  "installation_type": "Whole Current",
  "zone":        {"name": "Jaipur Zone 1", "code": "Z-01"},
  "circle":      {"name": "Circle 1",      "code": "C-01"},
  "division":    {"name": "Division 1",    "code": "D-01"},
  "subdivision": {"name": "Subdivision 1", "code": "SD-01"},
  "substation":  {"name": "Substation 1",  "code": "SS-01"},
  "feeder":      {"name": "Feeder 1",      "code": "F-001"},
  "dt":          {"name": "Malviya Nagar DT 1", "code": "DT-001"}
}
```

**Just the hierarchy**

```bash
curl -s "http://localhost:8000/meters/J100000" -H "Authorization: Bearer $TOKEN" \
  | jq '{zone,circle,division,subdivision,substation,feeder,dt}'
```

**Unknown meter → a real 404.** The portal answers `200` with the error buried in the body;
the service translates that into a proper status code.

```bash
curl -i "http://localhost:8000/meters/DOES-NOT-EXIST" -H "Authorization: Bearer $TOKEN"
```

```json
{"detail":"Meter not found"}
```

---

## `GET /meters/{meter_id}/consumption`

Half-hourly readings over the rolling ~7-day window the portal exposes — 337 readings per
meter, and there is no way to ask it for more (see PROTOCOL.md). `kwh` and `kvah` are
**cumulative register readings**, not per-interval usage; subtract consecutive values to get
consumption per slot.

| Param | Type | Default | Notes |
|---|---|---|---|
| `start` | ISO 8601 datetime | — | keep readings at or after this |
| `end` | ISO 8601 datetime | — | keep readings at or before this |
| `page` | int | `1` | min 1 |
| `page_size` | int | `100` | 1–5000 |

**Whole window**

```bash
curl "http://localhost:8000/meters/J100000/consumption" -H "Authorization: Bearer $TOKEN"
```

```json
{
  "data": [
    {
      "timestamp": "2026-06-23T23:30:00",
      "kwh": 48438.74,
      "kvah": 52313.84,
      "volt_r": 226.0
    }
  ],
  "total": 337,
  "page": 1,
  "page_size": 100
}
```

**Narrow to one day**

```bash
curl "http://localhost:8000/meters/J100000/consumption?start=2026-06-25T00:00:00&end=2026-06-25T23:59:59" \
  -H "Authorization: Bearer $TOKEN"
```

**Everything in one page**

```bash
curl "http://localhost:8000/meters/J100000/consumption?page_size=5000" \
  -H "Authorization: Bearer $TOKEN"
```

**Derive consumption per interval** — the service returns raw registers on purpose, so the
subtraction is yours to do

```bash
curl -s "http://localhost:8000/meters/J100000/consumption?page_size=5000" \
  -H "Authorization: Bearer $TOKEN" \
  | jq -r '[.data[].kwh] as $k | .data | to_entries[] | select(.key > 0)
           | "\(.value.timestamp)  \((($k[.key] - $k[.key-1]) * 1000 | round) / 1000)"'
```

```
2026-06-24T00:00:00  0.42
2026-06-24T00:30:00  0.42
2026-06-24T01:00:00  0.42
```

**Power factor** — kWh ÷ kVAh, the most useful thing derivable from these two registers

```bash
curl -s "http://localhost:8000/meters/J100000/consumption" -H "Authorization: Bearer $TOKEN" \
  | jq -r '.data[-1] | "power factor: \((.kwh / .kvah * 1000 | round) / 1000)"'
```

**Unknown meter → 404**, not a leaked portal error

```bash
curl -i "http://localhost:8000/meters/DOES-NOT-EXIST/consumption" -H "Authorization: Bearer $TOKEN"
```

---

## `GET /network/dts`

Distribution transformers and the feeder each one hangs off. The portal has no search on
this data at all — `q`, `search` and `query` are accepted and silently ignored — so every
filter here is provided by the service.

| Param | Type | Default | Notes |
|---|---|---|---|
| `search` | string | — | case-insensitive substring over `dt_code`, `name` or `feeder_code` |
| `dt_code` | string | — | exact, e.g. `DT-001` |
| `name` | string | — | exact, case-insensitive |
| `feeder_code` | string | — | exact, e.g. `F-003` |
| `capacity_kva` | int | — | `63`, `100`, `160`, `250`, `400` |
| `page` | int | `1` | min 1 |
| `page_size` | int | `20` | 1–1000 |

**All 40 transformers**

```bash
curl "http://localhost:8000/network/dts?page_size=1000" -H "Authorization: Bearer $TOKEN"
```

```json
{
  "data": [
    {
      "dt_code": "DT-001",
      "name": "Malviya Nagar DT 1",
      "feeder_code": "F-001",
      "capacity_kva": 100
    }
  ],
  "total": 40,
  "page": 1,
  "page_size": 1000
}
```

**Search and filter**

```bash
curl "http://localhost:8000/network/dts?search=Malviya"    -H "Authorization: Bearer $TOKEN"
curl "http://localhost:8000/network/dts?dt_code=DT-031"    -H "Authorization: Bearer $TOKEN"
curl "http://localhost:8000/network/dts?feeder_code=F-003" -H "Authorization: Bearer $TOKEN"
curl "http://localhost:8000/network/dts?capacity_kva=63"   -H "Authorization: Bearer $TOKEN"
```

**Feeders serving more than one transformer** — the hierarchy is not 1:1, and this is how
you see it: 40 DTs hang off only 28 feeders.

```bash
curl -s "http://localhost:8000/network/dts?page_size=1000" -H "Authorization: Bearer $TOKEN" \
  | jq -r '.data | group_by(.feeder_code)[] | select(length > 1)
           | "\(.[0].feeder_code): \(map(.dt_code) | join(", "))"'
```

**Total installed capacity**

```bash
curl -s "http://localhost:8000/network/dts?page_size=1000" -H "Authorization: Bearer $TOKEN" \
  | jq -r '[.data[].capacity_kva] | "\(add) kVA across \(length) DTs"'
```

---

## `POST /admin/cache/clear`

Drops the cached datasets so the next read pulls fresh from the portal, instead of waiting
out `CACHE_TTL_SECONDS` (default 300).

```bash
curl -X POST "http://localhost:8000/admin/cache/clear" -H "Authorization: Bearer $TOKEN"
```

```json
{"status":"cleared"}
```

The next `GET /meters` after this pays for a full refresh — 21 sequential requests to the
portal — so expect it to take a couple of seconds.

---

## Errors

| Status | When | Body |
|---|---|---|
| `401` | no token, malformed token, or expired token | `{"detail":"missing bearer token"}` / `{"detail":"invalid or expired token"}` |
| `401` | wrong credentials on `/auth/login` | `{"detail":"invalid credentials"}` |
| `404` | unknown meter on detail or consumption | `{"detail":"Meter not found"}` |
| `422` | bad query param — `page=0`, `page_size=99999`, unparseable date | FastAPI validation detail |
| `502` | the portal failed and no cached data was available | `{"detail":"portal request failed"}` |

**Reproduce each one**

```bash
# 401 - no token
curl -i "http://localhost:8000/meters"

# 401 - garbage token
curl -i "http://localhost:8000/meters" -H "Authorization: Bearer not-a-real-token"

# 404 - unknown meter
curl -i "http://localhost:8000/meters/NOPE" -H "Authorization: Bearer $TOKEN"

# 422 - page_size above the cap
curl -i "http://localhost:8000/meters?page_size=99999" -H "Authorization: Bearer $TOKEN"
```

---

## Smoke test

Hits every endpoint once and prints the status codes.

```bash
#!/usr/bin/env bash
BASE=http://localhost:8000
TOKEN=$(curl -s -X POST $BASE/auth/login -H 'content-type: application/json' \
  -d '{"username":"admin","password":"flock-energy-2026"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
AUTH="Authorization: Bearer $TOKEN"

check() { printf '%-46s %s\n' "$1" "$(curl -s -o /dev/null -w '%{http_code}' "${@:2}")"; }

check "GET  /health"                    $BASE/health
check "GET  /meters"                    -H "$AUTH" "$BASE/meters?page_size=5"
check "GET  /meters/J100000"            -H "$AUTH" "$BASE/meters/J100000"
check "GET  /meters/J100000/consumption" -H "$AUTH" "$BASE/meters/J100000/consumption?page_size=5"
check "GET  /network/dts"               -H "$AUTH" "$BASE/network/dts?page_size=5"
check "POST /admin/cache/clear"         -X POST -H "$AUTH" "$BASE/admin/cache/clear"
```
