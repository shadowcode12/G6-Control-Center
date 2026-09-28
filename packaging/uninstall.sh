#!/usr/bin/env bash
set -euo pipefail

echo "Removing G6 Control Center..."
sudo rm -rf /opt/g6-control-center
sudo rm -f /usr/local/bin/g6-control-center
sudo rm -f /usr/lib/g6-control-center/privileged_helper.py
sudo rmdir /usr/lib/g6-control-center 2>/dev/null || true
sudo rm -f /usr/share/applications/g6-control-center.desktop
sudo rm -f /usr/share/icons/hicolor/scalable/apps/g6-control-center.svg
echo "Uninstalled."
