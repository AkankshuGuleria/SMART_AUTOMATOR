"""
tasks/ — multi-step agent tasks and the "Needs from you" inbox.

Owns:    Persisting tasks/steps/needs locally, running task steps in order with
         approval gates, and resolving needs (secrets go to Windows Credential
         Manager or the project's .env — never to AUTOMATA's databases).
Never:   Runs an approval-gated step before the user approves it.
"""
