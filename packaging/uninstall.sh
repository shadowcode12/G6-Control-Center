#!/usr/bin/env bash
set -euo pipefail

echo "Removing G6 Control Center..."
sudo systemctl disable --now g6-control-center-keyboard.service 2>/dev/null || true
sudo systemctl disable --now g6-control-center-telemetry.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/g6-control-center-keyboard.service
sudo rm -f /etc/modprobe.d/g6-control-center-ec.conf
sudo rm -f /etc/systemd/system/g6-control-center-telemetry.service
sudo systemctl daemon-reload

sudo rm -rf /opt/g6-control-center
sudo rm -f /usr/local/bin/g6-control-center
sudo rm -f /usr/lib/g6-control-center/privileged_helper.py
sudo rmdir /usr/lib/g6-control-center 2>/dev/null || true
sudo rm -f /usr/share/applications/g6-control-center.desktop
sudo rm -f /usr/share/icons/hicolor/scalable/apps/g6-control-center.svg
sudo rm -rf /run/g6-control-center
sudo rm -rf /var/lib/g6-control-center

echo "Uninstalled."
