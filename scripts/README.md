# PHANTOM developer scripts

PowerShell helpers for local development on Windows. Run from the repository
root.

| Script | Purpose |
| --- | --- |
| `run-backend.ps1` | Start the FastAPI backend with the project venv |
| `run-web.ps1` | Start the Vite dev server for the web app |
| `run-tests.ps1` | Run the backend test suite |
| `check-web.ps1` | Typecheck, lint, and build the web app |
| `reset-output.ps1` | Clear generated artifacts under `output/` |

All scripts resolve paths relative to the repository root, so they work
regardless of the current directory.
