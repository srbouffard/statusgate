# statusgate

A lightweight FastAPI service that exposes a simple status dashboard and REST API for iterative agent workflows via a nice web UI rather than the CLI.  
An external agent can poll `/status` to check whether work is **pending / succeeded / failed** and retrieve context for corrective actions.

---

## Features

- **Web UI** – live-updating dashboard with status badge, context, and full history
- **REST API** – `GET /status` and `POST /status` with JSON payloads
- **Agent-friendly** – `retry_after` field and polling-ready design
- **In-memory store** – zero external dependencies; perfect for ephemeral workflows
- **Single-file binary** – build a self-contained Linux executable with `make build`

---

## Quick start (run directly)

```bash
make run          # creates .venv, installs deps, starts the server
```

Open <http://localhost:8000> in your browser.

---

## Build a self-contained Linux binary

```bash
make build
./dist/statusgate
```

The `Makefile` handles everything — Python venv creation, dependency installation, and PyInstaller bundling — without touching your system Python.

| Target | Description |
|--------|-------------|
| `make` / `make all` | Build the binary (default) |
| `make install` | Create `.venv` and install dependencies |
| `make run` | Run the server directly via the venv |
| `make build` | Produce `dist/statusgate` (single-file executable) |
| `make clean` | Remove build artefacts, keep `.venv` |
| `make distclean` | Remove build artefacts **and** `.venv` |
| `make help` | Print target descriptions |

> **Requirements:** Python 3.9+ available as `python3`. Override with `make PYTHON=python3.11 build`.

---

## API reference

### `GET /status`

Returns the current status entry.

```jsonc
{
  "status": "pending",          // "pending" | "success" | "failure"
  "context": "awaiting deploy",
  "timestamp": "2026-04-01T18:00:00Z",
  "last_updated": "2026-04-01T18:00:00Z",
  "retry_after": 5              // suggested polling interval (seconds)
}
```

### `POST /status`

Update the status and context.

```jsonc
// Request body
{
  "status": "success",
  "context": "All checks passed."
}
```

Returns the new status entry (HTTP 201).

### `GET /history`

Returns all previous entries (oldest first).

```jsonc
{ "history": [ { "status": "...", "context": "...", "timestamp": "..." }, ... ] }
```

---

## Agent polling example

```python
import time, requests

URL = "http://localhost:8000/status"

while True:
    data = requests.get(URL).json()
    if data["status"] != "pending":
        print("Done:", data["status"], data["context"])
        break
    time.sleep(data.get("retry_after", 5))
```

---

## Project layout

```
statusgate/
├── server.py      # FastAPI application (single script)
├── Makefile       # Build / run targets (Linux)
├── build.ps1      # Build script (Windows / PowerShell)
└── README.md
```
