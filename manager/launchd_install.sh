#!/bin/bash
# Instaluje / odinstalowuje daemon managera przez launchd.
# Użycie:
#   ./launchd_install.sh install   — zainstaluj i uruchom autostart
#   ./launchd_install.sh uninstall — usuń z launchd
#   ./launchd_install.sh start     — uruchom teraz (bez autostart)
#   ./launchd_install.sh stop      — zatrzymaj
#   ./launchd_install.sh status    — sprawdź status

set -euo pipefail

PLIST_SRC="$(cd "$(dirname "$0")" && pwd)/com.doomdoja.agent-manager.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.doomdoja.agent-manager.plist"
LABEL="com.doomdoja.agent-manager"
DAEMON_PY="$(cd "$(dirname "$0")" && pwd)/daemon.py"

case "${1:-help}" in
  install)
    echo "Instaluję LaunchAgent: $LABEL"
    cp "$PLIST_SRC" "$PLIST_DST"
    launchctl load -w "$PLIST_DST"
    echo "OK — daemon uruchomiony i skonfigurowany do autostartu."
    ;;
  uninstall)
    echo "Odinstalowuję LaunchAgent: $LABEL"
    launchctl unload -w "$PLIST_DST" 2>/dev/null || true
    rm -f "$PLIST_DST"
    echo "OK — daemon usunięty z launchd."
    ;;
  start)
    echo "Uruchamiam daemon (foreground, bez launchd)..."
    python3 "$DAEMON_PY" --start
    ;;
  stop)
    python3 "$DAEMON_PY" --stop
    ;;
  status)
    python3 "$DAEMON_PY" --status
    echo ""
    if launchctl list "$LABEL" &>/dev/null; then
      echo "launchd: zarejestrowany"
      launchctl list "$LABEL"
    else
      echo "launchd: NIE zarejestrowany"
    fi
    ;;
  *)
    echo "Użycie: $0 {install|uninstall|start|stop|status}"
    exit 1
    ;;
esac
