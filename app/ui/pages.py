from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.backend.battery import BatteryController
from app.backend.fans import FanController
from app.backend.graphics import GraphicsController
from app.backend.keyboard import KeyboardController
from app.backend.performance import PerformanceController
from app.backend.system_info import (
    get_cpu_frequency,
    get_cpu_temperature,
    get_cpu_usage,
    get_ram_usage,
    get_system_info,
)


def metric_card(title: str, value: str = "--", subtitle: str = "") -> QFrame:
    card = QFrame()
    card.setObjectName("card")

    layout = QVBoxLayout(card)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(5)

    title_label = QLabel(title)
    title_label.setObjectName("cardTitle")

    value_label = QLabel(value)
    value_label.setObjectName("cardValue")

    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("cardUnit")

    layout.addWidget(title_label)
    layout.addWidget(value_label)
    layout.addWidget(subtitle_label)

    card.value_label = value_label
    card.subtitle_label = subtitle_label
    return card


def page_header(title: str, subtitle: str) -> tuple[QLabel, QLabel]:
    title_label = QLabel(title)
    title_label.setObjectName("pageTitle")

    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("subtitle")

    return title_label, subtitle_label


def show_error(parent: QWidget, message: str) -> None:
    QMessageBox.warning(parent, "G6 Control Center", message)


class DashboardPage(QWidget):
    def __init__(
        self,
        performance: PerformanceController,
        battery: BatteryController,
        fans: FanController,
        graphics: GraphicsController,
    ):
        super().__init__()

        self.performance = performance
        self.battery = battery
        self.fans = fans
        self.graphics = graphics

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(18)

        title, subtitle = page_header(
            "Dashboard",
            "Live hardware status for your Gigabyte G6 KF",
        )
        layout.addWidget(title)
        layout.addWidget(subtitle)

        cards = QGridLayout()
        cards.setHorizontalSpacing(14)
        cards.setVerticalSpacing(14)

        self.cpu_card = metric_card("CPU", "--", "Temperature")
        self.gpu_card = metric_card("GPU", "--", "Temperature")
        self.ram_card = metric_card("RAM", "--", "Usage")
        self.gpu_power_card = metric_card("GPU POWER", "--", "Power draw")
        self.profile_card = metric_card("PROFILE", "--", "System profile")
        self.battery_card = metric_card("BATTERY", "--", "Charge")

        cards.addWidget(self.cpu_card, 0, 0)
        cards.addWidget(self.gpu_card, 0, 1)
        cards.addWidget(self.ram_card, 0, 2)
        cards.addWidget(self.gpu_power_card, 1, 0)
        cards.addWidget(self.profile_card, 1, 1)
        cards.addWidget(self.battery_card, 1, 2)

        layout.addLayout(cards)

        info_group = QGroupBox("System Snapshot")
        info_layout = QVBoxLayout(info_group)

        self.snapshot = QLabel("Reading hardware...")
        self.snapshot.setObjectName("info")
        self.snapshot.setWordWrap(True)
        info_layout.addWidget(self.snapshot)

        layout.addWidget(info_group)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
        self.refresh()

    def refresh(self) -> None:
        cpu_usage = get_cpu_usage()
        cpu_temp = get_cpu_temperature()
        cpu_freq = get_cpu_frequency()

        self.cpu_card.value_label.setText(
            f"{cpu_temp:.0f}°C" if cpu_temp is not None else "--"
        )

        ram_percent, used_gb, total_gb = get_ram_usage()
        self.ram_card.value_label.setText(f"{ram_percent:.0f}%")

        gpu = self.graphics.preferred_gpu()
        if gpu.get("available"):
            temperature = gpu.get("temperature")
            power = gpu.get("power")
            self.gpu_card.value_label.setText(
                f"{temperature:.0f}°C"
                if isinstance(temperature, (int, float))
                else "N/A"
            )
            self.gpu_power_card.value_label.setText(
                f"{power:.1f} W"
                if isinstance(power, (int, float))
                else "N/A"
            )
        else:
            self.gpu_card.value_label.setText("--")
            self.gpu_power_card.value_label.setText("N/A")

        profile = self.performance.current_profile()
        self.profile_card.value_label.setText(profile or "Unavailable")

        battery = self.battery.status()
        if battery.get("available") and battery.get("capacity") is not None:
            self.battery_card.value_label.setText(f"{battery['capacity']}%")
            self.battery_card.subtitle_label.setText(
                battery.get("state") or "Battery"
            )
        else:
            self.battery_card.value_label.setText("N/A")
            self.battery_card.subtitle_label.setText("Battery")

        fan_status = self.fans.status()
        fan_text = "Fans: unavailable"
        fans = fan_status.get("fans") or []
        if len(fans) >= 2:
            fan_text = (
                f"Fans: CPU {fans[0].get('rpm', 0)} RPM • "
                f"GPU {fans[1].get('rpm', 0)} RPM"
            )
        elif len(fans) == 1:
            fan_text = f"Fan: {fans[0].get('rpm', 0)} RPM"

        freq_text = (
            f"{cpu_freq / 1000:.2f} GHz"
            if cpu_freq
            else "N/A"
        )

        if gpu.get("available"):
            vendor = str(gpu.get("vendor", "gpu")).upper()
            gpu_name = gpu.get("name", vendor)
            gpu_usage = gpu.get("usage")
            gpu_usage_text = (
                f"{gpu_usage:.0f}%"
                if isinstance(gpu_usage, (int, float))
                else "N/A"
            )
            gpu_text = (
                f"{vendor} ({gpu_name}) • "
                f"GPU usage: {gpu_usage_text}"
            )
        else:
            gpu_text = "GPU telemetry unavailable"

        self.snapshot.setText(
            f"CPU usage: {cpu_usage:.0f}%   •   "
            f"CPU frequency: {freq_text}   •   "
            f"RAM: {used_gb:.1f} / {total_gb:.1f} GB   •   "
            f"{gpu_text}   •   {fan_text}"
        )


class PerformancePage(QWidget):
    def __init__(self, controller: PerformanceController):
        super().__init__()

        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(18)

        title, subtitle = page_header(
            "Performance",
            "System profiles and simple CPU energy preference",
        )
        layout.addWidget(title)
        layout.addWidget(subtitle)

        profile_group = QGroupBox("Performance Profiles")
        profile_layout = QGridLayout(profile_group)

        profiles = [
            ("silent", "Silent"),
            ("balanced", "Balanced"),
            ("performance", "Performance"),
            ("gaming", "Gaming"),
        ]

        self.profile_buttons: dict[str, QPushButton] = {}
        for index, (key, label) in enumerate(profiles):
            button = QPushButton(label)
            button.setObjectName("profileButton")
            button.setMinimumHeight(52)
            button.clicked.connect(
                lambda _=False, value=key: self.select_profile(value)
            )
            self.profile_buttons[key] = button
            profile_layout.addWidget(button, index // 2, index % 2)

        layout.addWidget(profile_group)

        cpu_group = QGroupBox("CPU Energy Preference")
        cpu_form = QFormLayout(cpu_group)

        self.driver_label = QLabel("--")
        self.epp_combo = QComboBox()
        for key in self.controller.EPP_OPTIONS:
            self.epp_combo.addItem(
                self.controller.EPP_LABELS[key],
                key,
            )

        self.epp_apply = QPushButton("Apply")
        self.epp_apply.clicked.connect(
            lambda: self.set_epp(
                self.epp_combo.currentData()
            )
        )

        cpu_form.addRow("CPU driver:", self.driver_label)
        epp_row = QHBoxLayout()
        epp_row.addWidget(self.epp_combo)
        epp_row.addWidget(self.epp_apply)
        cpu_form.addRow("Preference:", epp_row)

        note = QLabel(
            "Low = energy saving • Mid = balanced • High = performance. "
            "CPU power-limit and voltage controls are intentionally not exposed "
            "because the G6 KF firmware keeps those controls locked."
        )
        note.setObjectName("info")
        note.setWordWrap(True)
        cpu_form.addRow("", note)

        layout.addWidget(cpu_group)

        self.status = QLabel("Ready")
        self.status.setObjectName("info")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_state)
        layout.addWidget(
            self.refresh_button,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )

        layout.addStretch()
        self.refresh_state()

    def select_profile(self, profile: str) -> None:
        result = self.controller.set_profile(profile)
        if not result.ok:
            show_error(
                self,
                result.stderr or "Unable to change profile.",
            )
            return

        self.status.setText(
            f"Profile changed to {profile.title()}."
        )
        self.refresh_state()

    def set_epp(self, value: str | None) -> None:
        if not value:
            return

        result = self.controller.set_epp(value)
        if not result.ok:
            show_error(
                self,
                result.stderr or "Unable to set energy preference.",
            )
            return

        self.status.setText(
            f"Energy preference set to "
            f"{self.controller.EPP_LABELS.get(value, value.title())}."
        )
        self.refresh_state()

    def refresh_state(self) -> None:
        state = self.controller.state()

        self.driver_label.setText(
            state["driver"] or "Unavailable"
        )

        epp = state["epp"]
        if epp:
            blocked = self.epp_combo.blockSignals(True)
            index = self.epp_combo.findData(epp)
            if index >= 0:
                self.epp_combo.setCurrentIndex(index)
            self.epp_combo.blockSignals(blocked)

        available = set(
            self.controller.available_profiles()
        )
        for key, button in self.profile_buttons.items():
            button.setEnabled(
                self.controller.PROFILE_ALIASES[key]
                in available
            )

class GPUPage(QWidget):
    def __init__(self, controller: GraphicsController):
        super().__init__()
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(18)

        title, subtitle = page_header(
            "GPU",
            "Real-time Intel/NVIDIA telemetry and device information",
        )
        layout.addWidget(title)
        layout.addWidget(subtitle)

        cards = QGridLayout()
        self.temp_card = metric_card("TEMPERATURE", "--", "GPU")
        self.usage_card = metric_card("UTILIZATION", "--", "GPU")
        self.power_card = metric_card("POWER", "--", "Draw")
        self.vram_card = metric_card("VRAM", "--", "Used / total")
        self.clock_card = metric_card("CLOCK", "--", "Graphics")
        self.mode_card = metric_card("PRIME", "--", "Current mode")

        cards.addWidget(self.temp_card, 0, 0)
        cards.addWidget(self.usage_card, 0, 1)
        cards.addWidget(self.power_card, 0, 2)
        cards.addWidget(self.vram_card, 1, 0)
        cards.addWidget(self.clock_card, 1, 1)
        cards.addWidget(self.mode_card, 1, 2)
        layout.addLayout(cards)

        spec_group = QGroupBox("GPU Power Specification")
        spec_form = QFormLayout(spec_group)

        self.tgp_label = QLabel("--")
        self.default_power_label = QLabel("--")

        spec_form.addRow("Default TGP:", self.tgp_label)
        spec_form.addRow(
            "Driver default power:",
            self.default_power_label,
        )

        note = QLabel(
            "Power-limit, overclocking and undervolting controls are intentionally "
            "not exposed. The G6 KF firmware keeps these controls locked; the app "
            "only reports the driver's default power specification."
        )
        note.setObjectName("info")
        note.setWordWrap(True)
        spec_form.addRow("", note)

        layout.addWidget(spec_group)

        prime_group = QGroupBox("Graphics Mode")
        prime_layout = QHBoxLayout(prime_group)

        self.prime_combo = QComboBox()
        self.prime_combo.addItems(
            ["intel", "on-demand", "nvidia"]
        )

        self.prime_apply = QPushButton(
            "Apply (reboot required)"
        )
        self.prime_apply.clicked.connect(
            self.apply_prime_mode
        )

        prime_layout.addWidget(QLabel("PRIME:"))
        prime_layout.addWidget(self.prime_combo)
        prime_layout.addWidget(self.prime_apply)

        layout.addWidget(prime_group)

        self.status = QLabel("Reading GPU state...")
        self.status.setObjectName("info")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        layout.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
        self.refresh()

    @staticmethod
    def _value(
        value: object,
        suffix: str = "",
    ) -> str:
        if isinstance(value, (int, float)):
            return f"{value:.1f}{suffix}"
        return "N/A"

    def refresh(self) -> None:
        snapshot = self.controller.snapshot()
        gpu = snapshot.get("selected") or {}
        mode = snapshot.get("prime")

        if not gpu.get("available"):
            self.temp_card.value_label.setText("--")
            self.usage_card.value_label.setText("--")
            self.power_card.value_label.setText("--")
            self.vram_card.value_label.setText("--")
            self.clock_card.value_label.setText("--")
            self.mode_card.value_label.setText(
                mode or "N/A"
            )
            self.tgp_label.setText("N/A")
            self.default_power_label.setText("N/A")

            self.status.setText(
                "No live GPU telemetry source is available."
            )
        else:
            vendor = str(
                gpu.get("vendor", "gpu")
            ).upper()

            self.temp_card.value_label.setText(
                self._value(gpu.get("temperature"), "°C")
            )
            self.usage_card.value_label.setText(
                self._value(gpu.get("usage"), "%")
            )
            self.power_card.value_label.setText(
                self._value(gpu.get("power"), " W")
            )

            used = gpu.get("memory_used")
            total = gpu.get("memory_total")
            if (
                isinstance(used, (int, float))
                and isinstance(total, (int, float))
            ):
                self.vram_card.value_label.setText(
                    f"{used:.0f} / {total:.0f} MB"
                )
            else:
                self.vram_card.value_label.setText("N/A")

            clock = gpu.get("graphics_clock")
            self.clock_card.value_label.setText(
                f"{clock:.0f} MHz"
                if isinstance(clock, (int, float))
                else "N/A"
            )

            self.mode_card.value_label.setText(
                mode or "N/A"
            )

            if vendor == "NVIDIA":
                defaults = self.controller.get_default_power()
                default = defaults.get("default")
                text = (
                    f"{default:.0f} W"
                    if isinstance(default, (int, float))
                    else "N/A"
                )
                self.tgp_label.setText(text)
                self.default_power_label.setText(text)
            else:
                self.tgp_label.setText("N/A")
                self.default_power_label.setText(
                    "Intel telemetry"
                )

            self.status.setText(
                f"{gpu.get('name', 'GPU')} detected • "
                f"{vendor} telemetry • live"
            )

        if mode:
            blocked = self.prime_combo.blockSignals(True)
            index = self.prime_combo.findText(mode)
            if index >= 0:
                self.prime_combo.setCurrentIndex(index)
            self.prime_combo.blockSignals(blocked)

    def apply_prime_mode(self) -> None:
        mode = self.prime_combo.currentText()

        answer = QMessageBox.question(
            self,
            "Change Graphics Mode",
            f"Switch PRIME mode to '{mode}'? A reboot is required.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        ok, message = self.controller.set_prime_mode(mode)
        if not ok:
            show_error(
                self,
                message or "Unable to change PRIME mode.",
            )
            return

        self.status.setText(
            f"PRIME mode set to {mode}. "
            "Reboot Ubuntu to activate it."
        )

class FansPage(QWidget):
    def __init__(self, controller: FanController):
        super().__init__()
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(18)

        title, subtitle = page_header(
            "Fans",
            "Real-time fan RPM and EC telemetry",
        )
        layout.addWidget(title)
        layout.addWidget(subtitle)

        cards = QGridLayout()
        self.cpu_fan_card = metric_card("CPU FAN", "--", "RPM")
        self.gpu_fan_card = metric_card("GPU FAN", "--", "RPM")
        self.cpu_duty_card = metric_card("CPU DUTY", "--", "EC duty")
        self.gpu_duty_card = metric_card("GPU DUTY", "--", "EC duty")

        cards.addWidget(self.cpu_fan_card, 0, 0)
        cards.addWidget(self.gpu_fan_card, 0, 1)
        cards.addWidget(self.cpu_duty_card, 1, 0)
        cards.addWidget(self.gpu_duty_card, 1, 1)
        layout.addLayout(cards)

        info_group = QGroupBox("Fan Control")
        info_layout = QVBoxLayout(info_group)
        self.control_note = QLabel(
            "Manual per-fan control is intentionally disabled. "
            "On the G6 KF the EC behavior does not make independent fan "
            "control useful enough to expose as a normal feature. "
            "This build focuses on safe, live telemetry."
        )
        self.control_note.setWordWrap(True)
        info_layout.addWidget(self.control_note)
        layout.addWidget(info_group)

        status_group = QGroupBox("Native EC Status")
        status_layout = QVBoxLayout(status_group)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(150)
        status_layout.addWidget(self.output)
        layout.addWidget(status_group)

        layout.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(1000)
        self.refresh_status()

    def refresh_status(self) -> None:
        info = self.controller.status()
        fans = info.get("fans") or []

        if len(fans) >= 1:
            fan = fans[0]
            rpm = fan.get("rpm")
            duty = fan.get("duty_percent")
            self.cpu_fan_card.value_label.setText(
                f"{int(rpm)}" if isinstance(rpm, (int, float)) else "N/A"
            )
            self.cpu_duty_card.value_label.setText(
                f"{int(duty)}%"
                if isinstance(duty, (int, float))
                else "N/A"
            )
        else:
            self.cpu_fan_card.value_label.setText("N/A")
            self.cpu_duty_card.value_label.setText("N/A")

        if len(fans) >= 2:
            fan = fans[1]
            rpm = fan.get("rpm")
            duty = fan.get("duty_percent")
            self.gpu_fan_card.value_label.setText(
                f"{int(rpm)}" if isinstance(rpm, (int, float)) else "N/A"
            )
            self.gpu_duty_card.value_label.setText(
                f"{int(duty)}%"
                if isinstance(duty, (int, float))
                else "N/A"
            )
        else:
            self.gpu_fan_card.value_label.setText("N/A")
            self.gpu_duty_card.value_label.setText("N/A")

        if info.get("available"):
            source = info.get("source", "native")
            self.output.setPlainText(
                f"Source: {source}\n"
                f"EC telemetry: live\n"
                f"Independent fan writes: disabled"
            )
        else:
            self.output.setPlainText(
                info.get("reason")
                or "Native fan telemetry is unavailable."
            )


class RGBPage(QWidget):
    def __init__(self, controller: KeyboardController):
        super().__init__()
        self.controller = controller
        self.selected_color = "#00a2ff"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(18)

        title, subtitle = page_header(
            "RGB Lighting",
            "Native keyboard backend (EC RGB control is staged separately)",
        )
        layout.addWidget(title)
        layout.addWidget(subtitle)

        color_group = QGroupBox("Keyboard Color")
        color_layout = QHBoxLayout(color_group)

        self.color_preview = QFrame()
        self.color_preview.setFixedSize(48, 48)
        self.update_preview()

        color_button = QPushButton("Choose Color")
        color_button.clicked.connect(self.choose_color)

        self.hex_label = QLabel(self.selected_color)

        color_layout.addWidget(self.color_preview)
        color_layout.addWidget(self.hex_label)
        color_layout.addWidget(color_button)
        color_layout.addStretch()

        layout.addWidget(color_group)

        presets = QGroupBox("Presets")
        preset_layout = QHBoxLayout(presets)
        for name, value in (
            ("Red", "#ff0000"),
            ("Blue", "#008cff"),
            ("Green", "#00d26a"),
            ("Purple", "#a855f7"),
            ("White", "#ffffff"),
            ("Orange", "#ff7a18"),
        ):
            button = QPushButton(name)
            button.clicked.connect(
                lambda _=False, color=value: self.set_color(color)
            )
            preset_layout.addWidget(button)

        layout.addWidget(presets)

        brightness_group = QGroupBox("Brightness")
        brightness_layout = QHBoxLayout(brightness_group)

        self.brightness = QSlider(Qt.Orientation.Horizontal)
        self.brightness.setRange(0, 100)
        self.brightness.setValue(80)

        self.brightness_label = QLabel("80%")
        self.brightness.valueChanged.connect(
            lambda value: self.brightness_label.setText(f"{value}%")
        )

        brightness_layout.addWidget(self.brightness)
        brightness_layout.addWidget(self.brightness_label)

        apply_brightness = QPushButton("Apply")
        apply_brightness.clicked.connect(self.apply_brightness)
        brightness_layout.addWidget(apply_brightness)

        layout.addWidget(brightness_group)

        actions = QHBoxLayout()
        on_button = QPushButton("Keyboard ON")
        on_button.clicked.connect(self.turn_on)
        off_button = QPushButton("Keyboard OFF")
        off_button.clicked.connect(self.turn_off)
        apply_color = QPushButton("Apply Color")
        apply_color.clicked.connect(self.apply_color)

        actions.addWidget(apply_color)
        actions.addWidget(on_button)
        actions.addWidget(off_button)
        actions.addStretch()

        layout.addLayout(actions)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(140)
        layout.addWidget(self.output)

        layout.addStretch()
        self.refresh_status()

    def update_preview(self) -> None:
        self.color_preview.setStyleSheet(
            f"QFrame {{ background: {self.selected_color}; "
            "border-radius: 8px; border: 1px solid #3a4150; }}"
        )
        self.hex_label.setText(self.selected_color)

    def choose_color(self) -> None:
        color = QColorDialog.getColor(
            QColor(self.selected_color),
            self,
            "Select keyboard color",
        )
        if color.isValid():
            self.set_color(color.name())

    def set_color(self, color: str) -> None:
        self.selected_color = color.lower()
        self.update_preview()
        self.apply_color()

    def apply_color(self) -> None:
        result = self.controller.keyboard_color(self.selected_color)
        self.output.setPlainText(
            result.stdout
            or result.stderr
            or ("Color applied." if result.ok else "Unable to apply color.")
        )

    def apply_brightness(self) -> None:
        result = self.controller.keyboard_brightness(
            self.brightness.value()
        )
        self.output.setPlainText(
            result.stdout
            or result.stderr
            or ("Brightness applied." if result.ok else "Unable to apply brightness.")
        )

    def turn_on(self) -> None:
        result = self.controller.keyboard_on()
        self.output.setPlainText(
            result.stdout or result.stderr or "Keyboard backlight enabled."
        )

    def turn_off(self) -> None:
        result = self.controller.keyboard_off()
        self.output.setPlainText(
            result.stdout or result.stderr or "Keyboard backlight disabled."
        )

    def refresh_status(self) -> None:
        result = self.controller.keyboard_status()
        self.output.setPlainText(
            result.stdout
            or result.stderr
            or "gigactl keyboard status unavailable."
        )


class BatteryPage(QWidget):
    def __init__(self, controller: BatteryController):
        super().__init__()
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(18)

        title, subtitle = page_header(
            "Battery",
            "Live battery, charging and FlexiCharger-style limits",
        )
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.capacity_card = metric_card("CHARGE", "--", "Current")
        self.health_card = metric_card("HEALTH", "--", "Full / design")
        self.power_card = metric_card("POWER", "--", "Battery draw")
        self.limit_card = metric_card("LIMIT", "--", "Stop charging")

        cards = QGridLayout()
        cards.addWidget(self.capacity_card, 0, 0)
        cards.addWidget(self.health_card, 0, 1)
        cards.addWidget(self.power_card, 0, 2)
        cards.addWidget(self.limit_card, 1, 0)
        layout.addLayout(cards)

        group = QGroupBox("Charging Limit")
        form = QFormLayout(group)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(
            [
                "Full Charge",
                "Locked at 80%",
                "Custom",
            ]
        )
        self.mode_combo.currentTextChanged.connect(
            self._update_custom_visibility
        )

        self.start_combo = QComboBox()
        self.start_combo.addItems(
            [f"{value}%" for value in BatteryController.CLEVO_START_VALUES]
        )

        self.stop_combo = QComboBox()
        self.stop_combo.addItems(
            [f"{value}%" for value in BatteryController.CLEVO_END_VALUES]
        )

        self.apply_button = QPushButton("Apply Charging Mode")
        self.apply_button.clicked.connect(self.apply_mode)

        form.addRow("Mode:", self.mode_combo)

        self.start_label = QLabel("Start charging below:")
        self.stop_label = QLabel("Stop charging at:")

        form.addRow(
            self.start_label,
            self.start_combo,
        )
        form.addRow(
            self.stop_label,
            self.stop_combo,
        )
        form.addRow("", self.apply_button)

        note = QLabel(
            "Full Charge = 100%. Locked at 80% uses a 70% start / 80% stop "
            "cycle. Custom mode exposes the supported FlexiCharger-style "
            "start/stop thresholds. Custom thresholds are only enabled when "
            "Linux exposes both writable charging threshold interfaces."
        )
        note.setObjectName("info")
        note.setWordWrap(True)
        form.addRow("", note)

        layout.addWidget(group)

        details_group = QGroupBox("Battery Details")
        details_layout = QVBoxLayout(details_group)

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setMinimumHeight(150)
        details_layout.addWidget(self.details)

        layout.addWidget(details_group)

        self.status = QLabel("Reading battery...")
        self.status.setObjectName("info")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        layout.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
        self.refresh()

    def _update_custom_visibility(self, mode: str) -> None:
        custom = mode == "Custom"
        self.start_label.setVisible(custom)
        self.start_combo.setVisible(custom)
        self.stop_label.setVisible(custom)
        self.stop_combo.setVisible(custom)

    @staticmethod
    def _format_minutes(value: object) -> str:
        if not isinstance(value, (int, float)):
            return "N/A"
        total = max(0, int(value))
        hours, minutes = divmod(total, 60)
        return (
            f"{hours}h {minutes}m"
            if hours
            else f"{minutes}m"
        )

    def refresh(self) -> None:
        info = self.controller.status()

        if not info.get("available"):
            self.capacity_card.value_label.setText("N/A")
            self.health_card.value_label.setText("N/A")
            self.power_card.value_label.setText("N/A")
            self.limit_card.value_label.setText("Unsupported")
            self.apply_button.setEnabled(False)
            self.details.setPlainText(
                info.get("reason")
                or "No battery device detected."
            )
            self.status.setText(
                info.get("reason")
                or "No battery device detected."
            )
            return

        capacity = info.get("capacity")
        health = info.get("health")
        power = info.get("power_w")
        start = info.get("charge_start")
        stop = info.get("charge_limit")

        self.capacity_card.value_label.setText(
            f"{capacity}%"
            if isinstance(capacity, int)
            else "N/A"
        )
        self.health_card.value_label.setText(
            f"{health:.0f}%"
            if isinstance(health, (int, float))
            else "N/A"
        )
        self.power_card.value_label.setText(
            f"{power:.1f} W"
            if isinstance(power, (int, float))
            else "N/A"
        )
        self.limit_card.value_label.setText(
            f"{stop}%"
            if isinstance(stop, int)
            else "Unsupported"
        )

        if isinstance(start, int):
            index = self.start_combo.findText(f"{start}%")
            if index >= 0:
                self.start_combo.setCurrentIndex(index)

        if isinstance(stop, int):
            index = self.stop_combo.findText(f"{stop}%")
            if index >= 0:
                self.stop_combo.setCurrentIndex(index)

        supports_end = bool(info.get("supports_limit"))
        supports_custom = bool(info.get("supports_custom"))

        self.apply_button.setEnabled(
            supports_end or supports_custom
        )

        # Match UI mode to the actual current state.
        if stop == 100:
            mode = "Full Charge"
        elif stop == 80:
            mode = "Locked at 80%"
        elif supports_custom:
            mode = "Custom"
        else:
            mode = "Custom"

        blocked = self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentText(mode)
        self.mode_combo.blockSignals(blocked)
        self._update_custom_visibility(mode)

        charger = info.get("charger_connected")
        charger_text = (
            "Connected" if charger is True
            else "Disconnected" if charger is False
            else "Unknown"
        )

        lines = [
            f"Device: {info.get('name', 'Battery')}",
            f"State: {info.get('state') or 'Unknown'}",
            f"Charger: {charger_text}",
            (
                f"Voltage: {info['voltage_v']:.2f} V"
                if isinstance(info.get("voltage_v"), (int, float))
                else "Voltage: N/A"
            ),
            (
                f"Current: {info['current_a']:.2f} A"
                if isinstance(info.get("current_a"), (int, float))
                else "Current: N/A"
            ),
            (
                f"Time estimate: "
                f"{self._format_minutes(info.get('time_remaining_minutes'))}"
            ),
            (
                f"Charging thresholds: "
                f"{start}% → {stop}%"
                if isinstance(start, int) and isinstance(stop, int)
                else "Charging thresholds: unavailable"
            ),
        ]
        self.details.setPlainText("\n".join(lines))

        if supports_custom:
            self.status.setText(
                "Charge control available. "
                "Custom mode uses the kernel's reported threshold interface."
            )
        elif supports_end:
            self.status.setText(
                "Charge-stop control available. "
                "Custom start/stop control is not exposed."
            )
        else:
            self.status.setText(
                "Live battery telemetry is available, but the current Linux "
                "battery driver does not expose charge thresholds. "
                "For Clevo-family FlexiCharger support, a compatible "
                "clevo_acpi interface may be required."
            )

    def apply_mode(self) -> None:
        mode = self.mode_combo.currentText()

        if mode == "Full Charge":
            ok, message = self.controller.set_limit(100)
        elif mode == "Locked at 80%":
            ok, message = self.controller.set_limit(
                80,
                start_percent=70,
            )
        else:
            start = int(
                self.start_combo.currentText().rstrip("%")
            )
            stop = int(
                self.stop_combo.currentText().rstrip("%")
            )
            ok, message = self.controller.set_limit(
                stop,
                start_percent=start,
            )

        if not ok:
            show_error(
                self,
                message or "Unable to apply charging mode.",
            )
            return

        self.status.setText(
            f"{mode} charging mode applied."
        )
        self.refresh()

class SettingsPage(QWidget):
    def __init__(
        self,
        performance: PerformanceController,
        fans: FanController,
        graphics: GraphicsController,
        keyboard: KeyboardController,
    ):
        super().__init__()

        system = get_system_info()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(18)

        title, subtitle = page_header(
            "Settings",
            "System information, backend health and hardware status",
        )
        layout.addWidget(title)
        layout.addWidget(subtitle)

        system_group = QGroupBox("System")
        form = QFormLayout(system_group)
        form.addRow("Vendor:", QLabel(system["vendor"]))
        form.addRow("Model:", QLabel(system["model"]))
        form.addRow("Kernel:", QLabel(system["kernel"]))
        form.addRow("Platform:", QLabel(system["platform"]))
        layout.addWidget(system_group)

        deps_group = QGroupBox("Native Backend Availability")
        deps = QFormLayout(deps_group)
        graphics_snapshot = graphics.snapshot()
        nvidia = graphics_snapshot.get("nvidia") or {}
        intel = graphics_snapshot.get("intel") or {}

        deps.addRow(
            "Power profiles:",
            QLabel("Available" if performance.available else "Unavailable"),
        )
        deps.addRow(
            "Native EC telemetry:",
            QLabel("Available" if fans.available else "Unavailable"),
        )
        deps.addRow(
            "NVIDIA:",
            QLabel("Detected" if nvidia.get("available") else "Unavailable"),
        )
        deps.addRow(
            "Intel GPU:",
            QLabel("Detected" if intel.get("available") else "Unavailable"),
        )
        deps.addRow(
            "Native keyboard backend:",
            QLabel("Ready" if keyboard.available else "Staged / not enabled"),
        )
        layout.addWidget(deps_group)

        safety = QLabel(
            "Hardware boundary: this build does not use gigactl. "
            "The native fan backend is read-only and obtains G6 KF fan "
            "telemetry from the Linux EC interface through a small root-owned "
            "telemetry service. CPU and NVIDIA power controls still use "
            "standard Linux/NVIDIA interfaces and validate driver-reported ranges."
        )
        safety.setObjectName("info")
        safety.setWordWrap(True)
        layout.addWidget(safety)

        project = QLabel(
            "G6 Control Center\n"
            "Linux hardware management for Gigabyte G5/G6-class laptops\n"
            "GitHub: shadowcode12/G6-Control-Center"
        )
        project.setObjectName("info")
        layout.addWidget(project)

        layout.addStretch()


