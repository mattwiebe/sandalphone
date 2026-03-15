## Python Environment

- Use `uv` for Python environment and dependency management.
- Prefer `uv run ...` for Python commands and `uv sync` for environment setup.
- Do not create or manage Python virtual environments with `python -m venv` for this project.
- When deploying Python services, provision `uv` on the target host and install from the checked-in lockfile.
