# PROTOCOL — How Urja Meter Ops actually works

Reverse-engineered by inspecting network traffic in the browser (Chrome DevTools)
while using the portal as a normal logged-in operator. Nothing here required
bypassing auth or hitting endpoints outside a normal user's reach.

## Summary

**Stack:** SvelteKit app, session-cookie auth via better-auth.

**Data available, and how to get it:**

| Data | Endpoint |
|---|---|
| Meters — list/search/filter | `GET /portal/meters/search?q=<query>&page=<n>` |
| Meter detail + full network hierarchy (Zone→Circle→Division→Subdivision→Substation→Feeder→DT) | `GET /meters/<meterId>/__data.json` (SvelteKit internal page-data format, not a plain JSON API — see below) |
| DT/feeder summary list | `GET /portal/dts?page=<n>` |
| Consumption — half-hourly, rolling 7-day window | `GET /portal/meters/<meterId>/energy` |

**Auth:** `POST /login` (a SvelteKit form action, not a bespoke endpoint) →
sets a `__Secure-better-auth.session_token` cookie, 1-hour lifetime. Needs
an `Origin` header matching the portal's own origin or it's rejected with
`403` (SvelteKit's built-in CSRF check). Everything else just needs that
cookie sent back.

**Biggest quirks/surprises:**

1. Meter search's `pageSize` is hardcoded at 20 — passing `&pageSize=<n>`
   has no effect. No portal-side way to bulk-fetch more per call.
2. Meter detail/hierarchy isn't a REST endpoint at all — it's SvelteKit's
   internal client-navigation payload (`__data.json`), encoded in
   *devalue*'s flat reference format, which we had to write a small
   decoder for.
3. That same endpoint returns errors as HTTP `200` with the error embedded
   in the body, not as a 4xx status — easy to miss.
4. The network hierarchy looked deceptively 1:1 on a small sample (first
   page of meters had unique, sequential DT codes) but isn't — 403 meters
   map to only 40 DTs, and 40 DTs map to only 28 feeders, with uneven
   fan-out at both levels.
5. Consumption's numeric fields (`kwh`, `kvah`, `voltR`) are JSON strings,
   not numbers, and are cumulative register readings, not per-interval
   usage — "how much was consumed in this slot" requires computing a delta
   ourselves, which we chose not to do (see README's design notes).
6. Consumption is always a fixed rolling 7-day window — no date-range
   param, no "load more," confirmed by checking the exact first/last
   timestamps returned.

Full detail on each of these below.

## Stack

The portal is a **SvelteKit** application (confirmed via the `x-sveltekit-action`
header on form submissions, and `_app/immutable/...` JS chunk paths). Pages are
server-rendered SvelteKit routes; some pages additionally call a separate
internal JSON API under `/portal/*` for interactive data (search, pagination).

## Authentication

- Auth is handled by **better-auth** (confirmed via the session cookie name:
  `__Secure-better-auth.session_token`).
- Login: `POST /login`, `Content-Type: application/x-www-form-urlencoded`,
  body `email=...&password=...`, header `accept: application/json`.
  - This is a SvelteKit **form action**, not a bespoke API — the
    `x-sveltekit-action: true` header is what SvelteKit's `use:enhance` sets
    automatically on progressively-enhanced form submissions.
  - Response on success: `{"type":"redirect","status":303,"location":"/meters"}`
    — SvelteKit's standard form-action JSON envelope. On failure, expect a
    different `type` (not yet characterized — TODO: capture a bad-password
    response).
  - Response header sets the session cookie:
    `__Secure-better-auth.session_token=<opaque token>; Max-Age=3600; Path=/; HttpOnly; Secure; SameSite=Lax`
  - **Session lifetime is 1 hour.** Our client needs to re-authenticate on
    expiry rather than assume one login lasts the process lifetime.
- All subsequent requests just need that cookie sent back — no CSRF token
  required. However, **the login POST itself is rejected with `403
  Forbidden` unless an `Origin` header matching the portal's own origin is
  present** — this is SvelteKit's built-in CSRF protection for form actions
  (it checks `Origin` against the request host for non-GET, form-encoded
  submissions). A plain server-to-server POST without a browser-supplied
  `Origin` header fails until you add `Origin: https://urja-ops.flockenergy.tech`
  (a `Referer` header isn't strictly required, but was included to mirror the
  browser). This only affects the login action — the `/portal/*` GET
  endpoints have no such requirement.
- No evidence yet of a standalone better-auth REST surface (e.g.
  `/api/auth/get-session`) being used by the frontend — the app seems to
  route auth entirely through the `/login` SvelteKit action. Not yet checked
  whether such endpoints exist and respond if called directly.

## Data access

### Meter search / list

`GET /portal/meters/search?q=<query>&page=<n>`

- Plain JSON API (not a SvelteKit page route) — `accept: */*` is enough,
  returns `content-type: application/json` directly.
- `q` matches against meter number and/or serial number (confirmed:
  `q=SE33962` returns exactly the meter with that serial).
- `q=` (empty) returns the unfiltered list.
- Response shape:
  ```json
  {
    "data": [
      {
        "meterId": "J100000",
        "serialNo": "SE33962",
        "make": "HPL",
        "phaseType": "single",
        "installStatus": "Decommissioned",
        "dtCode": "DT-001"
      }
    ],
    "total": 403,
    "page": 1,
    "pageSize": 20
  }
  ```
- **Quirk:** `pageSize` is fixed at 20 — passing `&pageSize=<n>` does not
  change it (server ignores or overrides the param). There is no way to get
  more than 20 rows per request from the portal directly. Full-dataset pull
  requires paging through all `ceil(403/20) = 21` pages.
- Total dataset size is small (403 meters) — our API works around the fixed
  `pageSize` by pulling all 21 pages once into an in-memory cache (TTL
  refresh, see README design notes) and serving arbitrary `page`/`page_size`
  (up to 1000) plus extra filters (`make`, `status`, `phase_type`) from that
  cache rather than proxying the portal's pagination 1:1.

### Meter detail (and the full network hierarchy)

Unlike every other data source we found, this one is **not** a plain
`/portal/*` JSON endpoint. Guessed candidates (`/portal/meters/{id}`,
`/portal/meters/{id}/hierarchy`) don't exist. Instead it comes from
SvelteKit's internal client-navigation payload:

`GET /meters/<meterId>/__data.json`

This is what SvelteKit's router fetches instead of a full HTML page when
navigating client-side (e.g. clicking a meter link rather than typing the
URL). It works identically whether or not you pass
`?x-sveltekit-invalidated=001` (the query param the real browser sometimes
appends) — omit it and you get every node's data in one response instead of
some marked `{"type": "skip"}`, which is actually more convenient for a
server-to-server caller with no prior client state.

**Response shape** — `{"type": "data", "nodes": [...]}`. The last node holds
the actual page data, serialized in **devalue's flat reference format**:
`data` is a flat array where each slot is either a primitive (returned
as-is) or an object/array whose *values* are integer indices pointing at
other slots in the same array (object/array *keys* stay literal strings —
this tripped us up initially: a row like `{"parameterName": 5, "parameterValue": 1}`
resolves to `{"parameterName": "Meter ID", "parameterValue": "J100000"}`,
**not** `{"Meter ID": "J100000"}` — the key name itself is just a value
sitting in the array, same as any other string). Decoded example (`J100000`):

```json
{
  "meterId": "J100000",
  "detail": {
    "data": [
      {"parameterName": "Meter ID", "parameterValue": "J100000"},
      {"parameterName": "Serial No", "parameterValue": "SE33962"},
      {"parameterName": "Make", "parameterValue": "HPL"},
      {"parameterName": "Phase Type", "parameterValue": "single"},
      {"parameterName": "Installation Status", "parameterValue": "Decommissioned"},
      {"parameterName": "Installation Type", "parameterValue": "Whole Current"}
    ]
  },
  "hierarchy": {
    "Meter ID": "J100000",
    "Installation Status": "Decommissioned",
    "Installation Type": "Whole Current",
    "Zone": "Jaipur Zone 1 (Z-01)",
    "Circle": "Circle 1 (C-01)",
    "Division": "Division 1 (D-01)",
    "Subdivision": "Subdivision 1 (SD-01)",
    "Sub Station": "Substation 1 (SS-01)",
    "Feeder": "Feeder 1 (F-001)",
    "DT": "Malviya Nagar DT 1 (DT-001)"
  }
}
```

- **This reveals the full hierarchy**, deeper than `/portal/dts` alone
  showed: **Zone → Circle → Division → Subdivision → Substation → Feeder →
  DT → Meter.** Each hierarchy level is a `"Name (CODE)"` string that we
  split into separate name/code fields in our own API.
- One extra meter field not present in `/portal/meters/search`:
  `Installation Type` (e.g. "Whole Current").
- **Quirk: errors come back as HTTP `200`, not a 4xx status.** For an
  unknown meter ID, the leaf node is
  `{"type": "error", "error": {"message": "Meter not found"}, "status": 404}`
  — note `status` is a *sibling* of `error`, not nested inside it (easy to
  get wrong, we did on the first pass). Our API maps this to a real `404`
  rather than passing through the misleading `200`.

### Network hierarchy — DT/feeder summary list

`GET /portal/dts?page=<n>` — backs the "Transformers" nav page. Same
pagination envelope as meter search (`data`/`total`/`page`/`pageSize`,
capped at `pageSize=20`; `total=40`). Fields:

```json
{
  "code": "DT-001",
  "name": "Malviya Nagar DT 1",
  "feederCode": "F-001",
  "capacityKva": 100
}
```

- `code` matches the `dtCode` seen on meter records — confirms
  meter → DT is a real join key, not a coincidence.
- `feederCode` is the next level up. **This is not a clean 1:1 or even
  fan-out per DT** — across all 40 DTs there are only 28 unique feeder
  codes. Most feeders serve exactly one DT, but 12 of them serve two DTs
  each (e.g. `DT-031` "Malviya Nagar DT 31" has `feederCode: F-003`, not
  `F-031` — the naming looks 1:1 per-DT at a glance but isn't). Consistent
  with the assignment's warning that hierarchy data may be "messy or
  inconsistent" — don't assume a clean tree without checking.
- The levels above feeder (Substation, Subdivision, Division, Circle, Zone)
  are *not* exposed by this endpoint or any other plain `/portal/*`
  endpoint we found — they only surface via the per-meter `__data.json`
  above. There's no evidence of a `/portal/feeders`, `/portal/substations`,
  etc. list endpoint.
- Not yet confirmed whether `/portal/dts` accepts a search/query param the
  way `/portal/meters/search` does (`q=`) — only `page` has been observed
  in use.

### Consumption

`GET /portal/meters/<meterId>/energy` — backs the meter detail page's
consumption view. Example: `/portal/meters/J100000/energy`.

```json
{
  "data": [
    {"timestamp": "23/06/2026 23:30", "kwh": "48438.74", "kvah": "52313.84", "voltR": "226"},
    {"timestamp": "24/06/2026 00:00", "kwh": "48439.16", "kvah": "52314.29", "voltR": "229"}
  ]
}
```

- Half-hourly readings, `timestamp` as `DD/MM/YYYY HH:MM` (not ISO 8601).
- **Quirk:** `kwh`, `kvah`, and `voltR` are all JSON strings, not numbers
  (`"kwh": "48438.74"`) — needs explicit casting on our side.
- `kwh`/`kvah` look like **cumulative register readings** (monotonically
  increasing, ~0.42 kWh per 30-min slot in the sample seen), not
  per-interval consumption. If "recent consumption" should mean "how much
  was used in this period" rather than "what does the meter's register
  read," we'd need to derive that as a delta between consecutive readings
  ourselves — a deliberate design choice, not free from the portal.
- **No pagination envelope** on this endpoint (no `total`/`page`/`pageSize`,
  just `data`) — unlike `/portal/meters/search` and `/portal/dts`.
- **Confirmed: fixed rolling 7-day window**, not full history and no
  date-range param — checked on `J100000`: exactly 337 readings, spanning
  `2026-06-23 23:30` to `2026-06-30 23:30` (7 × 24 × 2 + 1, inclusive of
  both endpoints). The meter detail page has no date picker or "load more"
  control either — this is simply what "recent consumption" means on this
  portal.
- Unknown `meterId` returns a portal error (mapped to a clean `404` from our
  own API rather than leaking the portal's response) — confirmed via
  `GET /meters/DOES-NOT-EXIST/consumption`.

