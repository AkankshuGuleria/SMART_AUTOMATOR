"""
monitoring/ — local device telemetry for AUTOMATA.

Owns:    Host resource sampling (CPU, GPU, RAM, disk, network, processes) and
         foreground-app usage tracking.
Never:   Sends telemetry anywhere. Data stays on this machine; app usage is
         stored in a local SQLite file, not CockroachDB.
"""
