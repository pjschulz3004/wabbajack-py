#!/usr/bin/env bash
# wabbajack-py installer
# Usage: curl -fsSL https://raw.githubusercontent.com/pjschulz3004/wabbajack-py/master/install.sh | bash
set -euo pipefail

REPO="pjschulz3004/wabbajack-py"
INSTALL_DIR="${WABBAJACK_PY_DIR:-$HOME/.local/share/wabbajack-py}"
BIN_DIR="${HOME}/.local/bin"

info()  { printf '\033[1;34m::\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m::\033[0m %s\n' "$*"; }
err()   { printf '\033[1;31m::\033[0m %s\n' "$*" >&2; }

# ── Check dependencies ──────────────────────────────────────────────
info "Checking dependencies..."

command -v git >/dev/null || { err "git not found. Install it first."; exit 1; }
command -v python3 >/dev/null || { err "python3 not found. Install Python 3.10+."; exit 1; }

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    err "Python 3.10+ required (found $PY_VER)"
    exit 1
fi
ok "Python $PY_VER"

# ── Clone or update ─────────────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
    info "Updating existing install at $INSTALL_DIR..."
    git -C "$INSTALL_DIR" pull --ff-only
else
    info "Cloning wabbajack-py to $INSTALL_DIR..."
    git clone "https://github.com/$REPO.git" "$INSTALL_DIR"
fi

# ── Create venv and install ─────────────────────────────────────────
info "Setting up Python environment..."
VENV="$INSTALL_DIR/.venv"
if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
fi

"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -e "$INSTALL_DIR[all]" 2>&1 | tail -3

# ── Build frontend ──────────────────────────────────────────────────
FRONTEND="$INSTALL_DIR/frontend"
if [ -f "$FRONTEND/package.json" ]; then
    if command -v npm >/dev/null; then
        info "Building frontend..."
        cd "$FRONTEND"
        npm install --silent 2>/dev/null
        npx vite build --quiet 2>/dev/null || npx vite build 2>&1 | tail -5
        # Copy to static dir for serving
        STATIC="$INSTALL_DIR/src/wabbajack/web/static"
        mkdir -p "$STATIC"
        cp -r dist/* "$STATIC/" 2>/dev/null || true
        cd "$INSTALL_DIR"
        ok "Frontend built"
    else
        info "npm not found, skipping frontend build (CLI still works)"
    fi
fi

# ── Create launcher script ──────────────────────────────────────────
mkdir -p "$BIN_DIR"
LAUNCHER="$BIN_DIR/wabbajack-py"

cat > "$LAUNCHER" << 'SCRIPT'
#!/usr/bin/env bash
INSTALL_DIR="${WABBAJACK_PY_DIR:-$HOME/.local/share/wabbajack-py}"
exec "$INSTALL_DIR/.venv/bin/python" -m wabbajack.cli "$@"
SCRIPT
chmod +x "$LAUNCHER"

# ── Verify ──────────────────────────────────────────────────────────
ok "Installed wabbajack-py v$("$VENV/bin/python" -c 'from wabbajack import __version__; print(__version__)')"
ok "Location: $INSTALL_DIR"
ok "Command:  $LAUNCHER"

# Check if BIN_DIR is in PATH
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
    info "Add to your shell profile:"
    echo "  export PATH=\"$BIN_DIR:\$PATH\""
fi

echo ""
ok "Run: wabbajack-py serve"
ok "Update: wabbajack-py update"
