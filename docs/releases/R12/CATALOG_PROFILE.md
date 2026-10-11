# Catalog profiling checkpoint

2026-10-11; development checkpoint, not R12 acceptance.

The same isolated SQLite database contained 1,000 published products, 1,000
variants and 2,000 available offers from two approved synthetic sellers. Each
product had a 4,400-character description and a 5,000-character specification.
There were no image files. Thirty samples followed one excluded warmup for each
case. RequestFactory invoked public views in-process in the same scratch runtime;
no HTTP server, concurrent users, PostgreSQL, Redis or external providers were
involved. Timings are descriptive and sensitive to runtime noise.

| Case | Before p95 ms | After p95 ms | Maximum queries after |
|---|---:|---:|---:|
| Listing | 40.639 | 19.750 | 2 |
| Price sorting | 46.545 | 15.517 | 2 |
| Search | 22.884 | 19.679 | 2 |
| Category | 44.552 | 15.845 | 3 |
| Suggestions | 6.728 | 4.487 | 1 |
| Detail | 2.225 | 2.176 | 3 |
| Related | 19.917 | 11.346 | 3 |

The implementation defers description/specification columns for listing cards
and limits related products to eight in SQL rather than loading fifty and then
slicing. Query counts and response sizes did not change in this dataset. Changes
in suggestions/detail are noise rather than evidence of an optimization there.
Raw reports: [before](catalog-before.json), [after](catalog-after.json).

Regression tests use 31 products with approved media metadata to verify constant
query budgets, SQL row limits, deterministic pagination and image responses.
The profiler is read-only, allows 1–200 iterations and refuses output overwrite:

```bash
cd backend
python manage.py benchmark_catalog --iterations 30 --output /tmp/catalog-profile.json
```

Repeat on a representative PostgreSQL staging database with real catalog/media
distribution, capture HTTP p95 under concurrent load, examine EXPLAIN plans and
record hardware before choosing indexes, caching or an independent search engine.
This local result does not establish launch SLOs or justify service extraction.
