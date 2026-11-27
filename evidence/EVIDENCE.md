# Evidence pack — gold-dashboard t_d058408b (2026-11-27T07:17:53Z)

## pytest
......................................                                   [100%]
38 passed in 9.85s

## endpoint sweep (backend 127.0.0.1:8600, frontend 127.0.0.1:8601)
health       200
bias         200
structure    200
options      200
macro        200
schedule     200
snapshots    200
weekly       200
frontend     200

## bias live (headline)
{'score': -60.5, 'label': 'Strong bearish', 'reliability': 0.875, 'dimensions_used': ['cot', 'etf', 'macro', 'options', 'structure']}
per-dim reliability: {'structure': 1.0, 'options': 0.6, 'macro': 1.0, 'cot': 0.97, 'etf': 1.0}

## refresh live (real collectors from VPS)
{
    "GC=F": {
        "status": "ok",
        "rows": 101
    },
    "DX-Y.NYB": {
        "status": "ok",
        "rows": 101
    },
    "fred": {
        "status": "ok",
        "rows": 30
    },
    "cftc": {
        "status": "ok",
        "rows": 30
    },
    "tv_options": {
        "status": "ok",
        "rows": 1
    },
    "cme_snapshots": {
        "status": "skipped",
        "reason": "GITHUB_DATA_TOKEN not configured (D10)"
    },
    "all_failed": false
}

## docker
gold-backend	Up 2 minutes (healthy)	127.0.0.1:8600->8000/tcp
gold-frontend	Up 23 minutes	127.0.0.1:8601->3000/tcp
