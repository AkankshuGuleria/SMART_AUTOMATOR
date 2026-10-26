"""
workspace/ — continuity of the developer's working state.

Owns:    Which project is active, the capture threads that follow it, session
         snapshots ("where I left off") and resuming from them.
Never:   Talks to model providers or CockroachDB directly.
"""
