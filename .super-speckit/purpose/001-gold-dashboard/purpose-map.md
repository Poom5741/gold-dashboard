# Purpose Map — 001-gold-dashboard

## Intended outcome
Web dashboard on Poom's VPS aggregating free macro/positioning/options/market-structure data into an explainable weekly directional bias for gold, with scheduled reports and reproducible metrics

## People affected
Poom (owner, sole user); dev (Hermes worker, builder); independent QA subagent

## Success signal
SPEC.md section 9 acceptance criteria all pass: runs on single VPS via docker compose, no paid data, automated weekly brief, daily bias with visible evidence, historical snapshots, stale/missing data flagged, reproducible metrics, no look-ahead; pytest green; live curl checks on deployed endpoints

## Non-goals
no automated trade execution, no real-time tick streaming, no paid feeds, no ML price prediction, no broker integration, no position management

## Human purpose gate
This map is a draft. A human confirms that this is the intended purpose, or corrects it. Technical implementation choices are deliberately outside this gate.
