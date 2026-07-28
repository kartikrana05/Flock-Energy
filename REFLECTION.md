# Reflection

## What assumptions did you make?

The clearest one: I assumed the portal's meter-search endpoint would behave
like a normal paginated API where `pageSize` is respected. Testing showed
otherwise — passing `pageSize=100` (or any other value) has no effect; the
response is hardcoded to 20 rows per page regardless. That assumption
breaking is actually what shaped a real design decision: since the backend
won't let us ask for more per call, our own API pulls the full dataset into
an in-memory cache instead of trying to proxy the portal's pagination
directly (see README's Notes section for the full design rationale). Other
assumptions — like treating the
portal's fixed 7-day consumption window as simply "what recent consumption
means here" rather than something we could widen — are documented in the
README's Notes section.

## Which part was the most difficult, and how did you get unstuck?

The hardest part was deciding how to cache data sensibly. With only 403
meters today, pulling everything into memory works fine and keeps the
design simple — but that's a scale-dependent choice, not a universal one.
A real utility's dataset could be orders of magnitude larger, at which
point holding everything in a Python list in memory stops being
appropriate and you'd want a real database or a precomputed/persisted
store instead. I got unstuck by treating this explicitly as a documented
trade-off rather than trying to over-engineer a "future-proof" solution for
a scale that doesn't exist in this dataset — sized the solution to the
actual 403-meter/40-DT dataset in front of me, and wrote down what would
need to change if that assumption stopped holding.

## If you had another day, what would you improve?

I'd focus specifically on the computation/storage layer, since an API like
this is meant to support real integrations, and a real distribution
utility's dataset could be lakhs or crores of records, not a few hundred.
The in-memory full-dataset caching approach that works well here would need
to be replaced with something backed by an actual database with proper
indexing for the filters this API supports, rather than linear scans over
an in-memory list — the current design would start struggling well before
that scale.

## What mistake did you make while solving this?

While decoding the portal's SvelteKit `__data.json` payload (used for
meter detail and the full network hierarchy), I misread how its
reference-encoding worked. I assumed a row like
`{"parameterName": 5, "parameterValue": 1}` would resolve into
`{"Meter ID": "J100000"}`, but it actually resolves into
`{"parameterName": "Meter ID", "parameterValue": "J100000"}` — object keys
stay literal strings, only the values are references into the flat array.
That wrong assumption shipped as working-looking code and only surfaced as
a `KeyError` when I actually tested `GET /meters/J100000` end-to-end
rather than just eyeballing the decoder logic. A second, related bug came
from the same underlying carelessness: I initially read the error status
from the wrong place in the payload (nested inside `error` instead of
being its sibling), which silently turned every "meter not found" case into
a `500` instead of a `404`. Both were only caught by testing against the
live portal, not by re-reading the code.

## If you were reviewing your own submission, what would you criticise?

Two things, honestly. First, the caching/computation approach is sized for
today's small dataset and would need real work — a proper datastore,
indexing, maybe incremental sync — before it holds up at production scale;
it's a reasonable trade-off for this assignment but I'd flag it as the
first thing to revisit. Second, a fair amount of the markdown documentation
in this repo (PROTOCOL.md, the design-decision docs, this file) was written
with AI assistance rather than fully by hand. The investigation itself —
the actual portal exploration, the curls, the discoveries — was mine, and
I made a point of driving that part directly rather than delegating it, but
the writing-up was collaborative, and I think that's worth being upfront
about rather than presenting the docs as if I typed every line myself.
