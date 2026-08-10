# Architecture

The CLI is GAMR's primary entry point. The web app and API are optional interfaces for starting
starting experiments and visualizing shared run bundles.

```mermaid
flowchart LR
    CLI["CLI · primary"] --> Service["Shared execution service"]
    API["FastAPI · optional"] --> Queue["Bounded in-process queue"] --> Service
    Web["React · optional"] --> API
    Service --> Engine["gamr-engine"]
    Engine --> Core["gamr-core"]
    Service --> Adapters["JSON, Tyr, model adapters"]
    CLI --> Bundles[".gamr JSON bundles"]
    API --> Bundles
    Bundles --> API
```

`gamr-core` owns validated contracts. `gamr-engine` owns workflow and shared finalization.
`gamr-adapters` owns provider and filesystem I/O. Apps compose these packages without duplicating
experiment logic or invoking CLI subprocesses.

One API process owns service scheduling. The default concurrency is three; additional runs wait
FIFO. JSON is authoritative, while activity search and relationship views are derived in memory.
The filesystem and scheduler boundaries stay narrow so a demonstrated future deployment need can
replace either without changing the engine.
