#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="/opt/g6-control-center"
HELPER_DIR="/usr/lib/g6-control-center"
BIN="/usr/local/bin/g6-control-center"

command -v python3 >/dev/null || { echo "python3 is required."; exit 1; }
command -v sudo >/dev/null || { echo "sudo is required."; exit 1; }

echo "[1/6] Installing application to ${PREFIX}"
sudo mkdir -p "${PREFIX}" "${HELPER_DIR}"
sudo rm -rf "${PREFIX}/app"
sudo cp -a "${ROOT}/app" "${PREFIX}/app"
sudo cp "${ROOT}/pyproject.toml" "${ROOT}/README.md" "${PREFIX}/"

if [ ! -x "${PREFIX}/venv/bin/python" ]; then
  echo "[2/6] Creating application virtual environment"
  sudo python3 -m venv "${PREFIX}/venv"
fi

echo "[3/6] Installing Python dependencies"
sudo "${PREFIX}/venv/bin/pip" install --upgrade pip
sudo "${PREFIX}/venv/bin/pip" install "${PREFIX}"

echo "[4/6] Installing trusted privileged helper"
sudo install -m 0755 "${ROOT}/app/services/privileged_helper.py" "${HELPER_DIR}/privileged_helper.py"

echo "[5/6] Installing launcher and desktop entry"
sudo tee "${BIN}" >/dev/null <<EOF
#!/usr/bin/env bash
exec "${PREFIX}/venv/bin/python" -m app.main
EOF
sudo chmod 0755 "${BIN}"
sudo install -m 0644 "${ROOT}/assets/g6-control-center.desktop" /usr/share/applications/g6-control-center.desktop

if [ -f "${ROOT}/assets/g6-control-center.svg" ]; then
  sudo install -d /usr/share/icons/hicolor/scalable/apps
  sudo install -m 0644 "${ROOT}/assets/g6-control-center.svg" /usr/share/icons/hicolor/scalable/apps/g6-control-center.svg
fi

echo "[6/6] Installing native hardware telemetry service"
sudo install -m 0644 "${ROOT}/assets/g6-control-center-ec.conf" /etc/modprobe.d/g6-control-center-ec.conf
# Load optional Clevo ACPI support when the running kernel provides it.
sudo /usr/sbin/modprobe clevo_acpi 2>/dev/null || true
sudo install -m 0644 "${ROOT}/assets/g6-control-center-telemetry.service" /etc/systemd/system/g6-control-center-telemetry.service
sudo systemctl daemon-reload
sudo systemctl enable --now g6-control-center-telemetry.service
sudo install -m 0644 "${ROOT}/assets/g6-control-center-keyboard.service" /etc/systemd/system/g6-control-center-keyboard.service
sudo systemctl daemon-reload
sudo systemctl enable g6-control-center-keyboard.service
sudo systemctl start g6-control-center-keyboard.service || true

echo
echo "Installed. Launch with: g6-control-center"
