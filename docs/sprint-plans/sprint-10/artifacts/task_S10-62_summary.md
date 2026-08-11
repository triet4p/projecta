# Task Summary: S10-62 — Clean-Compose acceptance runner

Added `scripts/run_sprint10_acceptance.ps1` and a real-browser JSON/Mock
journey. The runner builds an isolated production-shaped Compose stack, waits
for liveness/readiness, executes all seven acceptance labels, restarts API/web/
PostgreSQL, scans correlated logs for secrets/RDF/raw fixture references, and
always removes clean volumes.

Testing: acceptance-runner contract tests passed. On clean validation commit
`c2789f915ab72f98779c0d710a7d14280510bf2d`, the production-shaped run passed
all seven journeys: real-browser `2 passed`, evidence lifecycle `11 passed`,
idempotent replay `1 passed`, project isolation `9 passed`, failure truthfulness
`3 passed`, and recovery `2 passed`. Post-restart browser persistence passed
`1/1`; correlation and safe-log scans passed; isolated volumes were removed.
