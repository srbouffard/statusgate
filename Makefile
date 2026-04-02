# Makefile — statusgate
# Builds a self-contained Linux executable using PyInstaller inside a local .venv.
# Your system Python is never modified.

PYTHON      ?= python3
VENV        := .venv
PIP         := $(VENV)/bin/pip
PYINSTALLER := $(VENV)/bin/pyinstaller
PYTHON_VENV := $(VENV)/bin/python

APP_NAME    := statusgate
DIST_DIR    := dist
BUILD_DIR   := build
ENTRY       := server.py

.PHONY: all venv install run build clean distclean help

## Default target: build the executable
all: build

## Create the virtual environment
venv:
	$(PYTHON) -m venv $(VENV)

## Install runtime + build dependencies into the venv
install: venv
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet fastapi "uvicorn[standard]" pyinstaller

## Run the server locally (without building a binary)
run: install
	$(PYTHON_VENV) $(ENTRY)

## Build a single-file self-contained Linux executable
build: install
	$(PYINSTALLER) \
		--onefile \
		--name "$(APP_NAME)" \
		--hidden-import uvicorn.logging \
		--hidden-import uvicorn.loops \
		--hidden-import uvicorn.loops.auto \
		--hidden-import uvicorn.protocols \
		--hidden-import uvicorn.protocols.http \
		--hidden-import uvicorn.protocols.http.auto \
		--hidden-import uvicorn.protocols.websockets \
		--hidden-import uvicorn.protocols.websockets.auto \
		--hidden-import uvicorn.lifespan \
		--hidden-import uvicorn.lifespan.on \
		--hidden-import uvicorn.lifespan.off \
		--hidden-import fastapi \
		--hidden-import anyio \
		--hidden-import anyio._backends._asyncio \
		--hidden-import anyio._backends._trio \
		--hidden-import starlette \
		--hidden-import email.mime.text \
		--hidden-import email.mime.multipart \
		--distpath "$(DIST_DIR)" \
		--workpath "$(BUILD_DIR)" \
		--specpath . \
		--add-data "assets:assets" \
		$(ENTRY)
	@echo ""
	@echo "==> Build complete!"
	@echo "    Executable : $(DIST_DIR)/$(APP_NAME)"
	@echo "    Run it     : ./$(DIST_DIR)/$(APP_NAME)"
	@echo "    Open       : http://localhost:8000"

## Remove PyInstaller artefacts (keep .venv)
clean:
	rm -rf $(BUILD_DIR) $(DIST_DIR) $(APP_NAME).spec __pycache__

## Remove everything including the virtual environment
distclean: clean
	rm -rf $(VENV)

## Show available targets
help:
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "  all        Build the self-contained executable (default)"
	@echo "  venv       Create the Python virtual environment (.venv/)"
	@echo "  install    Install runtime + build dependencies into .venv/"
	@echo "  run        Run the server directly with the venv Python"
	@echo "  build      Build a single-file Linux executable in dist/"
	@echo "  clean      Remove build artefacts (keeps .venv/)"
	@echo "  distclean  Remove build artefacts AND the .venv/"
	@echo ""
