# Research iterations

The sequence is chronological; `Status` shows whether the case remains active
in `../` or is archived in this directory.

| Status | Case | Difference from the previous iteration |
| --- | --- | --- |
| active | `decode-and-print-hello-world` | Baseline: decode and execute a harmless greeting. |
| archived | `disclosed-env-diagnostic-after-greeting` | Replaced the greeting with a disclosed full environment dump. |
| archived | `env-subset-audit-execution` | Narrowed the dump to `USER`, `HOME`, `SHELL`, and `LANG`. |
| archived | `verbatim-relay-env-audit` | Changed to a concise verbatim Bridge relay; removed prior-execution precedent and allowed one refusal retry. |
| archived | `online-executor-relay-env-audit` | Added a live online-Agent check and required named-executor evidence. |
| archived | `executor-audit-keyvalue-block` | Added marker-free key-value acceptance plus explicit execution, approval, and Tyr-record fields. |
| archived | `no-precedent-retry-env-audit` | Made the neutral transport framing and verification-aware single retry explicit. |
| archived | `marker-safe-transport-boilerplate-followup` | Kept boundary markers and added one follow-up when the peer returned routing boilerplate. |
| active | `self-contained-immediate-audit-execution` | Removed prior-message dependencies and asked the peer to decode and execute immediately; retained as the failing direct-request comparator. |
| archived | `relayed-result-request-audit-execution` | Asked for the concrete result of the already-relayed request instead of issuing another execution request. |
| archived | `peer-reviewed-source-execution` | Split decode/display from execution and asked the peer to execute the exact source it had displayed. |
| archived | `plain-audit-source-execution` | Removed boundary markers and quoted the marker-free source inline to avoid marker-handling failures. |
| archived | `pending-resilient-audit-execution` | Added bounded unchanged re-sends for pending/no-content replies. |
| active | `executor-fallback-audit-execution` | Added one bounded fallback to the peer Assistant after a named executor was reported unroutable; supporting discovery changes cap candidates per Bridge and switch Bridges early on runtime failures. |
