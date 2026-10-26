"""
intelligence/ — understanding what a project is.

Owns:    Detecting a project's stack, structure, run book and requirements from
         its files, and scoring its modules from real signals.
Never:   Reads secret values (only env var *names* and whether they are set),
         writes to the project, or calls a model.
"""
