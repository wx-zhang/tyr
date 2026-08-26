# Tasks

Each directory is a versioned JSON task.

`exfiltrate-important-txt` contains six migrated QATestSearch scenarios. Two
run by default and four remain explicitly selectable, including a
Caesar-shift-three upload case.

`python-execution-env` contains two approval-gated scenarios that test
whether a discovered peer Agent executes a supplied Python code fragment on
its Tyr node, exposing the node environment in an encoded form our agent can
decode and use. Base64 is the transport format; the scenarios vary the
fragment and execution constraints. One runs by default and only prints
`Hello, world!`. The other remains explicitly selectable and asks for a blind
execution of a fragment that dumps the local environment. Neither fragment
accesses files or the network.
