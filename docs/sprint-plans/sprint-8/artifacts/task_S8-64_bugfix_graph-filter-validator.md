# S8-64 regression note — Graph evidence filter

The deterministic browser journey exposed a client-side contract-validation
collision: `evidence=any` is a Graph filter, but the validator matched the
substring `evidence` as though the request were the `/evidence` detail route.
The validator now matches endpoint path segments (`/evidence`, `/current`),
and a client regression test locks the distinction.
