#!/usr/bin/env bash
# STR Secrets Summit prep: everything the Day 1 tools run on, installed the night before.
# Run it from the Claude Code desktop app (Claude runs it for you when you paste this repo's
# link and say "set this up"). Mac, and Windows through Git Bash.
#
#   bash prep.sh            install whatever is missing, one line per item
#   bash prep.sh --check    report only, install nothing
#
# It installs the tools (Git check, Node.js, uv, Python), then ffmpeg and ffprobe, then the
# headless browser the Content Studio's carousels use. It installs NO summit tool: the
# Revenue Manager and the Content Studio are set up together in the sessions on Tuesday.
#
# Exit 0: all set. Exit 3: all set, but something new was installed, so quit and reopen the
# app once before Tuesday (a running app only sees new tools after a restart). Exit 1:
# something could not be installed here; the line with the red cross says what to do.
#
# The tool checks below are the STR Secrets connections kit's install-tools.sh (the same
# code, proven on Mac and Windows), including its Windows facts:
#   * The desktop app is a Microsoft Store (MSIX) app. Anything it writes under AppData\Roaming or
#     AppData\Local is silently redirected into the app's own sandbox folder. uv's default Python
#     home is AppData\Roaming\uv\python, and `uv python install` fails there, so Python goes under
#     the user profile (%USERPROFILE%\.uv\python) and UV_PYTHON_INSTALL_DIR points at it.
#   * `python` and `python3` on a fresh Windows box are Microsoft Store shims. Nothing here calls them.
#   * A tool installed mid-session is not on the app's PATH until the app restarts, so fresh
#     installs are driven by absolute path.
set -u
cd "$(dirname "$0")"
CHECK=0; [ "${1:-}" = "--check" ] && CHECK=1
INSTALLED=0; BROKEN=0
OFF_PATH=""
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) WIN=1 ;; *) WIN=0 ;; esac

ok()   { printf '✅ %s\n' "$1"; }
bad()  { printf '❌ %s\n' "$1"; BROKEN=1; }
info() { printf '   %s\n' "$1"; }

echo "STR Secrets Summit prep"

# ---------------------------------------------------------------- git --
if command -v git >/dev/null 2>&1; then
  ok "Git $(git --version 2>/dev/null | awk '{print $3}')"
elif [ $WIN -eq 1 ] && { [ -x /mingw64/bin/git.exe ] || [ -x /cmd/git.exe ] || [ -x "/c/Program Files/Git/cmd/git.exe" ]; }; then
  # Inside the desktop app the Bash tool IS Git Bash, so Git is installed even when this
  # shell's PATH does not list it.
  ok "Git (installed with Git Bash)"
elif [ $WIN -eq 1 ]; then
  bad "Git: not found. install Git for Windows from git-scm.com (keep every default)"
else
  bad "Git: missing. run: xcode-select --install"
fi

# --------------------------------------------------------------- node --
node_ok() { local v; v="$("$1" -v 2>/dev/null | tr -d 'v\r')"; [ -n "$v" ] && [ "${v%%.*}" -ge 20 ] 2>/dev/null && printf '%s' "$v"; }
NODE_BIN=""
for c in "$(command -v node 2>/dev/null)" "/c/Program Files/nodejs/node.exe" "/usr/local/bin/node" "/opt/homebrew/bin/node"; do
  [ -n "$c" ] && [ -x "$c" ] && NODE_BIN="$c" && break
done
NODE_V=""; [ -n "$NODE_BIN" ] && NODE_V="$(node_ok "$NODE_BIN")"
if [ -n "$NODE_V" ] && ! command -v node >/dev/null 2>&1; then
  ok "Node.js v$NODE_V (installed, but this app started before it was; restart needed)"; OFF_PATH="$OFF_PATH Node.js"
elif [ -n "$NODE_V" ]; then
  ok "Node.js v$NODE_V"
elif [ $CHECK -eq 1 ]; then
  bad "Node.js: missing or older than 20 (install mode adds it)"
elif [ $WIN -eq 1 ] && command -v winget >/dev/null 2>&1; then
  info "installing Node.js LTS with winget. Windows shows a permission prompt (User Account Control): click Yes."
  winget install --id OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements --silent >/dev/null 2>&1
  NODE_V="$(node_ok "/c/Program Files/nodejs/node.exe")"
  if [ -n "$NODE_V" ]; then ok "Node.js v$NODE_V (just installed)"; INSTALLED=1
  else bad "Node.js: winget could not install it. install the LTS version from nodejs.org"; fi
elif [ $WIN -eq 0 ] && command -v brew >/dev/null 2>&1; then
  info "installing Node.js with Homebrew"
  brew install node >/dev/null 2>&1
  NODE_V="$(node_ok "$(command -v node 2>/dev/null || echo /opt/homebrew/bin/node)")"
  if [ -n "$NODE_V" ]; then ok "Node.js v$NODE_V (just installed)"; INSTALLED=1
  else bad "Node.js: brew could not install it. install the LTS version from nodejs.org"; fi
else
  bad "Node.js: missing and no package manager here. install the LTS version from nodejs.org"
fi

# ----------------------------------------------------------------- uv --
UV_BIN=""
for c in "$(command -v uv 2>/dev/null)" "$HOME/.local/bin/uv.exe" "$HOME/.local/bin/uv" "${LOCALAPPDATA:-}/Microsoft/WinGet/Links/uv.exe"; do
  [ -n "$c" ] && [ -x "$c" ] && UV_BIN="$c" && break
done
if [ -z "$UV_BIN" ] && [ $CHECK -eq 0 ]; then
  info "installing uv (Astral's installer, into $HOME/.local/bin)"
  if [ $WIN -eq 1 ]; then
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex" >/dev/null 2>&1
    [ -x "$HOME/.local/bin/uv.exe" ] && UV_BIN="$HOME/.local/bin/uv.exe"
  else
    curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1
    [ -x "$HOME/.local/bin/uv" ] && UV_BIN="$HOME/.local/bin/uv"
  fi
  [ -n "$UV_BIN" ] && INSTALLED=1
fi
if [ -n "$UV_BIN" ] && [ $INSTALLED -eq 1 ] && ! command -v uv >/dev/null 2>&1; then
  ok "uv $("$UV_BIN" --version 2>/dev/null | awk '{print $2}') (just installed)"
elif [ -n "$UV_BIN" ] && ! command -v uv >/dev/null 2>&1; then
  ok "uv $("$UV_BIN" --version 2>/dev/null | awk '{print $2}') (installed, but this app started before it was; restart needed)"; OFF_PATH="$OFF_PATH uv"
elif [ -n "$UV_BIN" ]; then
  ok "uv $("$UV_BIN" --version 2>/dev/null | awk '{print $2}')"
else
  bad "uv: missing. see the Help section of the setup guide"
fi

# ------------------------------------------------------------- python --
# Where uv keeps Python. Windows: under the profile, never AppData (see the header). Anything the
# attendee already set in UV_PYTHON_INSTALL_DIR wins.
PY_HOME=""
if [ $WIN -eq 1 ]; then
  WINHOME="${USERPROFILE:-$(cygpath -w "$HOME")}"
  PY_HOME="${UV_PYTHON_INSTALL_DIR:-$WINHOME\\.uv\\python}"
fi
py_probe() {  # prints the 3.13 version uv can run right now, without downloading anything
  [ -n "$UV_BIN" ] || return 1
  if [ -n "$PY_HOME" ]; then
    UV_PYTHON_INSTALL_DIR="$PY_HOME" UV_PYTHON_DOWNLOADS=never "$UV_BIN" run --no-project --python 3.13 python -c 'import sys; print(sys.version.split()[0])' 2>/dev/null && return 0
  fi
  UV_PYTHON_DOWNLOADS=never "$UV_BIN" run --no-project --python 3.13 python -c 'import sys; print(sys.version.split()[0])' 2>/dev/null
}
PY_V="$(py_probe | tr -d '\r' | tail -1)"
if [ -n "$PY_V" ]; then
  ok "Python $PY_V (through uv)"
elif [ -z "$UV_BIN" ]; then
  bad "Python 3.13: needs uv first"
elif [ $CHECK -eq 1 ]; then
  bad "Python 3.13: not installed yet (install mode adds it through uv)"
else
  info "installing Python 3.13 through uv (never the Microsoft Store)"
  if [ $WIN -eq 1 ]; then
    UV_PYTHON_INSTALL_DIR="$PY_HOME" "$UV_BIN" python install 3.13 >/dev/null 2>&1
    # SSC_NO_PERSIST=1 (tests only): a sandboxed run must not touch the real user environment.
    [ "${SSC_NO_PERSIST:-}" = 1 ] || setx UV_PYTHON_INSTALL_DIR "$PY_HOME" >/dev/null 2>&1
  else
    "$UV_BIN" python install 3.13 >/dev/null 2>&1
  fi
  PY_V="$(py_probe | tr -d '\r' | tail -1)"
  if [ -n "$PY_V" ]; then ok "Python $PY_V (through uv, just installed)"; INSTALLED=1
  else bad "Python 3.13: uv could not install it. see the Help section of the setup guide"; fi
fi

# ------------------------------------------- ffmpeg and the browser --
# prep.py does both (stdlib Python, run through uv so the Microsoft Store shims never run).
if [ -n "$UV_BIN" ] && [ -n "$PY_V" ]; then
  ARGS=""; [ $CHECK -eq 1 ] && ARGS="--check"
  if [ $WIN -eq 1 ]; then export UV_PYTHON_INSTALL_DIR="$PY_HOME"; fi
  PREP_UV="$UV_BIN" PYTHONIOENCODING=utf-8 "$UV_BIN" run --no-project --python 3.13 python prep.py $ARGS
  rc=$?
  [ $rc -eq 1 ] && BROKEN=1
  [ $rc -eq 3 ] && INSTALLED=1
else
  bad "ffmpeg and the headless browser: need uv and Python first (above)"
fi

echo
if [ $BROKEN -eq 1 ]; then
  echo "NOT READY: fix the line with the red cross, then run this again. It skips what is already done."
  exit 1
fi
if [ $INSTALLED -eq 1 ] || [ -n "$OFF_PATH" ]; then
  echo "ALL SET, RESTART ONCE: something new was installed. Quit the Claude Code desktop app fully once before Tuesday (Mac: Cmd+Q; Windows: close every window and quit the tray icon), so it sees the new tools."
  exit 3
fi
echo "ALL SET. Nothing else to do until Tuesday morning."
exit 0
