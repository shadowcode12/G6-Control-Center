import sys

from PySide6.QtCore import QTimer
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

from app.backend.system_info import (
    get_cpu_temperature,
    get_cpu_usage,
    get_ram_usage,
)
from app.backend.nvidia import get_gpu_info
from app.ui.performance_page import PerformancePage


class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")

        subtitle = QLabel("G6 KF hardware overview")
        subtitle.setObjectName("subtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(15)

        self.cpu_card = self.create_card("CPU", "--", "Temperature")
        self.gpu_card = self.create_card("GPU", "--", "Temperature")
        self.ram_card = self.create_card("RAM", "--", "Usage")
        self.power_card = self.create_card("GPU Power", "--", "Power")

        cards_layout.addWidget(self.cpu_card)
        cards_layout.addWidget(self.gpu_card)
        cards_layout.addWidget(self.ram_card)
        cards_layout.addWidget(self.power_card)

        layout.addLayout(cards_layout)

        self.status_label = QLabel("Reading hardware...")
        self.status_label.setObjectName("info")

        layout.addWidget(self.status_label)
        layout.addStretch()

        # Update hardware information every 1 second
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_hardware)
        self.timer.start(1000)

        # First update immediately
        self.update_hardware()

    def create_card(self, title, value, unit):
        card = QFrame()
        card.setObjectName("card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)

        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")

        value_label = QLabel(value)
        value_label.setObjectName("cardValue")

        unit_label = QLabel(unit)
        unit_label.setObjectName("cardUnit")

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(unit_label)

        card.value_label = value_label

        return card

    def update_hardware(self):
        # CPU
        cpu_usage = get_cpu_usage()
        cpu_temp = get_cpu_temperature()

        if cpu_temp is not None:
            self.cpu_card.value_label.setText(
                f"{cpu_temp:.0f}°C"
            )
        else:
            self.cpu_card.value_label.setText("--")

        # GPU
        gpu = get_gpu_info()

        if gpu.get("available"):
            self.gpu_card.value_label.setText(
                f"{gpu['temperature']:.0f}°C"
            )

            self.power_card.value_label.setText(
                f"{gpu['power']:.1f} W"
            )
        else:
            self.gpu_card.value_label.setText("--")
            self.power_card.value_label.setText("--")

        # RAM
        ram_percent, used_gb, total_gb = get_ram_usage()

        self.ram_card.value_label.setText(
            f"{ram_percent:.0f}%"
        )

        self.status_label.setText(
            f"CPU Usage: {cpu_usage:.0f}%   |   "
            f"RAM: {used_gb:.1f} / {total_gb:.1f} GB   |   "
            f"GPU: "
            f"{gpu.get('usage', 0):.0f}%"
            if gpu.get("available")
            else
            f"CPU Usage: {cpu_usage:.0f}%   |   "
            f"RAM: {used_gb:.1f} / {total_gb:.1f} GB   |   "
            f"GPU: Not available"
        )


class SimplePage(QWidget):
    def __init__(self, title_text):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel(title_text)
        title.setObjectName("pageTitle")

        layout.addWidget(title)
        layout.addStretch()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("G6 Control Center")
        self.resize(1150, 720)

        central = QWidget()
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 25, 20, 20)

        logo = QLabel("G6")
        logo.setObjectName("logo")

        app_name = QLabel("Control Center")
        app_name.setObjectName("appName")

        sidebar_layout.addWidget(logo)
        sidebar_layout.addWidget(app_name)
        sidebar_layout.addSpacing(25)

        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")

        pages = [
            "Dashboard",
            "Performance",
            "GPU",
            "Fans",
            "RGB",
            "Battery",
            "Settings",
        ]

        for page in pages:
            self.navigation.addItem(QListWidgetItem(page))

        sidebar_layout.addWidget(self.navigation)
        sidebar_layout.addStretch()

        status = QLabel("●  System Ready\n   G6 KF")
        status.setObjectName("status")

        sidebar_layout.addWidget(status)

        # Pages
        self.stack = QStackedWidget()

        self.stack.addWidget(DashboardPage())
        self.stack.addWidget(PerformancePage())
        self.stack.addWidget(SimplePage("GPU"))
        self.stack.addWidget(SimplePage("Fans"))
        self.stack.addWidget(SimplePage("RGB"))
        self.stack.addWidget(SimplePage("Battery"))
        self.stack.addWidget(SimplePage("Settings"))

        self.navigation.currentRowChanged.connect(
            self.stack.setCurrentIndex
        )

        self.navigation.setCurrentRow(0)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.stack)

        self.setCentralWidget(central)

        self.apply_styles()

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background: #0f1117;
            }

            QWidget {
                color: #e6e9ef;
                font-family: "Ubuntu";
                font-size: 14px;
            }

            #sidebar {
                background: #171a22;
                border-right: 1px solid #292d38;
            }

            #logo {
                font-size: 34px;
                font-weight: bold;
                color: #ff6b2c;
            }

            #appName {
                font-size: 18px;
                font-weight: bold;
            }

            #navigation {
                background: transparent;
                border: none;
                outline: none;
            }

            #navigation::item {
                padding: 13px;
                margin: 3px 0;
                border-radius: 8px;
            }

            #navigation::item:selected {
                background: #272c3a;
                color: #ff7a3d;
            }

            #navigation::item:hover {
                background: #20242e;
            }

            #status {
                color: #7be495;
                padding: 10px;
            }

            #pageTitle {
                font-size: 30px;
                font-weight: bold;
            }

            #subtitle {
                color: #8d94a3;
                font-size: 15px;
            }

            #card {
                background: #181c25;
                border: 1px solid #292e3a;
                border-radius: 12px;
                min-height: 150px;
            }

            #cardTitle {
                color: #9299a8;
                font-size: 15px;
            }

            #cardValue {
                font-size: 34px;
                font-weight: bold;
            }

            #cardUnit {
                color: #737b8b;
            }

            #info {
                background: #181c25;
                border: 1px solid #292e3a;
                border-radius: 12px;
                padding: 20px;
                color: #9da4b3;
            }
        """)


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()