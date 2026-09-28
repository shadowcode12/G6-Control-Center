from __future__ import annotations

import sys

from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.backend.battery import BatteryController
from app.backend.gigactl import GigaCtlController
from app.backend.nvidia import NvidiaController
from app.backend.performance import PerformanceController
from app.ui.pages import (
    BatteryPage,
    DashboardPage,
    FansPage,
    GPUPage,
    PerformancePage,
    RGBPage,
    SettingsPage,
)
from app.version import APP_VERSION
from app.ui.tray import TrayController


APP_STYLE = """
QMainWindow {
    background: #0d1016;
}

QWidget {
    color: #e8ecf4;
    font-family: "Ubuntu";
    font-size: 14px;
}

QFrame#sidebar {
    background: #151922;
    border-right: 1px solid #272d3a;
}

QLabel#logo {
    font-size: 38px;
    font-weight: 800;
    color: #ff6b2c;
}

QLabel#appName {
    font-size: 18px;
    font-weight: 700;
}

QLabel#version {
    color: #737c8e;
    font-size: 12px;
}

QListWidget#navigation {
    background: transparent;
    border: none;
    outline: none;
}

QListWidget#navigation::item {
    padding: 12px;
    margin: 3px 0;
    border-radius: 9px;
}

QListWidget#navigation::item:selected {
    background: #252b39;
    color: #ff8150;
}

QListWidget#navigation::item:hover {
    background: #1e2330;
}

QLabel#status {
    color: #71e59a;
    padding: 8px;
}

QLabel#pageTitle {
    font-size: 31px;
    font-weight: 800;
}

QLabel#subtitle {
    color: #929aaa;
    font-size: 15px;
}

QFrame#card {
    background: #171c26;
    border: 1px solid #292f3c;
    border-radius: 13px;
    min-height: 125px;
}

QLabel#cardTitle {
    color: #8f98aa;
    font-size: 13px;
    font-weight: 600;
}

QLabel#cardValue {
    color: #f2f5fa;
    font-size: 31px;
    font-weight: 800;
}

QLabel#cardUnit {
    color: #70798a;
    font-size: 12px;
}

QGroupBox {
    background: #141923;
    border: 1px solid #292f3c;
    border-radius: 12px;
    margin-top: 10px;
    padding: 18px;
    font-weight: 700;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 8px;
    color: #dce2ec;
}

QPushButton {
    background: #202634;
    border: 1px solid #303849;
    border-radius: 9px;
    padding: 9px 14px;
}

QPushButton:hover {
    background: #293043;
}

QPushButton:pressed {
    background: #31394d;
}

QPushButton:disabled {
    color: #5f6675;
    background: #171b24;
}

QPushButton#profileButton {
    min-height: 50px;
    font-size: 15px;
    font-weight: 700;
}

QComboBox, QSpinBox, QDoubleSpinBox {
    background: #1a1f2a;
    border: 1px solid #303747;
    border-radius: 8px;
    padding: 7px;
}

QSlider::groove:horizontal {
    height: 6px;
    background: #2a3040;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    width: 16px;
    margin: -5px 0;
    border-radius: 8px;
    background: #ff6b2c;
}

QTextEdit, QLabel#info {
    background: #171c26;
    border: 1px solid #292f3c;
    border-radius: 10px;
    padding: 12px;
    color: #a6afbf;
}
"""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("G6 Control Center")
        self.resize(1180, 760)
        self.setMinimumSize(980, 650)

        self.performance = PerformanceController()
        self.nvidia = NvidiaController()
        self.gigactl = GigaCtlController()
        self.battery = BatteryController()

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = self._build_sidebar()
        content = QFrame()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        self.pages = [
            DashboardPage(
                self.performance,
                self.battery,
                self.gigactl,
                self.nvidia,
            ),
            PerformancePage(self.performance),
            GPUPage(self.nvidia),
            FansPage(self.gigactl),
            RGBPage(self.gigactl),
            BatteryPage(self.battery),
            SettingsPage(
                self.performance,
                self.gigactl,
                self.nvidia,
            ),
        ]

        for page in self.pages:
            self.stack.addWidget(page)

        content_layout.addWidget(self.stack)

        root.addWidget(sidebar)
        root.addWidget(content)

        self.setCentralWidget(central)
        self.setStyleSheet(APP_STYLE)
        self.tray_controller = TrayController(self, self.performance)
        self.tray_controller.show()

        self.navigation.currentRowChanged.connect(
            self.stack.setCurrentIndex
        )
        self.navigation.setCurrentRow(0)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(235)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 24, 20, 20)

        logo = QLabel("G6")
        logo.setObjectName("logo")

        app_name = QLabel("Control Center")
        app_name.setObjectName("appName")

        version = QLabel(f"v{APP_VERSION}")
        version.setObjectName("version")

        layout.addWidget(logo)
        layout.addWidget(app_name)
        layout.addWidget(version)
        layout.addSpacing(20)

        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")

        for name in (
            "Dashboard",
            "Performance",
            "GPU",
            "Fans",
            "RGB",
            "Battery",
            "Settings",
        ):
            self.navigation.addItem(QListWidgetItem(name))

        layout.addWidget(self.navigation)
        layout.addStretch()

        status = QLabel(
            "●  System Ready\n"
            "   Gigabyte G6 KF"
        )
        status.setObjectName("status")
        layout.addWidget(status)

        return sidebar


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("G6 Control Center")
    app.setOrganizationName("G6 Control Center")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
