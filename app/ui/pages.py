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
            "Linux-native power management and CPU controls",
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

        cpu_group = QGroupBox("CPU Controls")
        cpu_form = QFormLayout(cpu_group)

        self.driver_label = QLabel("--")
        self.epp_combo = QComboBox()
        self.epp_combo.addItems(self.controller.EPP_OPTIONS)

        self.epp_apply = QPushButton("Apply EPP")
        self.epp_apply.clicked.connect(
            lambda: self.set_epp(self.epp_combo.currentText())
        )

        self.turbo_button = QPushButton("Toggle Turbo")
        self.turbo_button.clicked.connect(self.toggle_turbo)

        self.turbo_label = QLabel("--")

        cpu_form.addRow("CPU driver:", self.driver_label)
        epp_row = QHBoxLayout()
        epp_row.addWidget(self.epp_combo)
        epp_row.addWidget(self.epp_apply)
        cpu_form.addRow("Energy preference:", epp_row)
        cpu_form.addRow("Turbo status:", self.turbo_label)
        cpu_form.addRow("", self.turbo_button)

        layout.addWidget(cpu_group)

        rapl_group = QGroupBox("CPU Power Limits (RAPL)")
        self.rapl_layout = QGridLayout(rapl_group)
        self.rapl_message = QLabel("Detecting Intel RAPL power limits...")
        self.rapl_layout.addWidget(self.rapl_message, 0, 0, 1, 4)
        layout.addWidget(rapl_group)

        self.status = QLabel("Ready")
        self.status.setObjectName("info")
        layout.addWidget(self.status)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_state)
        layout.addWidget(self.refresh_button, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch()
        self.refresh_state()

    def select_profile(self, profile: str) -> None:
        result = self.controller.set_profile(profile)
        if not result.ok:
            show_error(self, result.stderr or "Unable to change profile.")
            return
        self.status.setText(f"Profile changed to {profile.title()}.")
        self.refresh_state()

    def set_epp(self, value: str) -> None:
        if not value or not self.controller.energy_performance_preference():
            return
        result = self.controller.set_epp(value)
        if not result.ok:
            # Combo box signals during startup should not create popups.
            if self.isVisible():
                show_error(self, result.stderr or "Unable to set EPP.")
        else:
            self.status.setText(f"Energy preference set to {value}.")
            self.refresh_state()

    def toggle_turbo(self) -> None:
        current = self.controller.turbo_enabled()
        if current is None:
            show_error(self, "Turbo control is not exposed by this kernel.")
            return

        result = self.controller.set_turbo_enabled(not current)
        if not result.ok:
            show_error(self, result.stderr or "Unable to change Turbo.")
            return

        self.status.setText(
            f"Turbo Boost {'enabled' if not current else 'disabled'}."
        )
        self.refresh_state()

    def refresh_state(self) -> None:
        state = self.controller.state()

        self.driver_label.setText(state["driver"] or "Unavailable")
        self.turbo_label.setText(
            "ON" if state["turbo"] is True
            else "OFF" if state["turbo"] is False
            else "Unavailable"
        )

        epp = state["epp"]
        if epp:
            block = self.epp_combo.blockSignals(True)
            index = self.epp_combo.findText(epp)
            if index >= 0:
                self.epp_combo.setCurrentIndex(index)
            self.epp_combo.blockSignals(block)

        available = set(self.controller.available_profiles())
        for key, button in self.profile_buttons.items():
            button.setEnabled(
                self.controller.PROFILE_ALIASES[key] in available
            )

        self.render_rapl(state["rapl"])

    def render_rapl(self, constraints) -> None:
        while self.rapl_layout.count():
            item = self.rapl_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not constraints:
            message = QLabel(
                "Intel RAPL power limits are not exposed on this kernel."
            )
            self.rapl_layout.addWidget(message, 0, 0)
            return

        headers = ["Limit", "Current", "Range", "Apply"]
        for column, header in enumerate(headers):
            self.rapl_layout.addWidget(QLabel(header), 0, column)

        for row, constraint in enumerate(constraints, start=1):
            name = QLabel(
                "PL1" if constraint.index == 0 else "PL2"
            )
            current = QLabel(f"{constraint.current_watts:.1f} W")

            spin = QDoubleSpinBox()
            spin.setDecimals(1)
            spin.setSingleStep(1.0)
            spin.setSuffix(" W")
            spin.setValue(constraint.current_watts)

            if constraint.min_watts is not None:
                spin.setMinimum(constraint.min_watts)
            else:
                spin.setMinimum(1.0)

            if constraint.max_watts is not None:
                spin.setMaximum(constraint.max_watts)
            else:
                spin.setMaximum(200.0)

            apply_button = QPushButton("Apply")
            apply_button.clicked.connect(
                lambda _=False, idx=constraint.index, box=spin:
                self.apply_rapl(idx, box.value())
            )

            range_text = (
                f"{constraint.min_watts:.1f}-{constraint.max_watts:.1f} W"
                if constraint.min_watts is not None
                and constraint.max_watts is not None
                else "Kernel range unavailable"
            )

            self.rapl_layout.addWidget(name, row, 0)
            self.rapl_layout.addWidget(current, row, 1)
            self.rapl_layout.addWidget(QLabel(range_text), row, 2)
            self.rapl_layout.addWidget(apply_button, row, 3)

    def apply_rapl(self, index: int, watts: float) -> None:
        result = self.controller.set_rapl_limit(index, watts)
        if not result.ok:
            show_error(self, result.stderr or "Unable to set CPU power limit.")
            return
        self.status.setText(f"Power limit {index} set to {watts:.1f} W.")
        self.refresh_state()


class GPUPage(QWidget):
    def __init__(self, controller: GraphicsController):
        super().__init__()
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(18)

        title, subtitle = page_header(
            "GPU",
            "Real-time Intel/NVIDIA telemetry and supported controls",
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

        power_group = QGroupBox("GPU Power Limit")
        power_form = QFormLayout(power_group)

        self.power_spin = QDoubleSpinBox()
        self.power_spin.setDecimals(1)
        self.power_spin.setSuffix(" W")
        self.power_spin.setEnabled(False)

        self.default_power = QLabel("--")
        power_form.addRow("Default:", self.default_power)
        power_form.addRow("Requested:", self.power_spin)

        self.power_apply = QPushButton("Apply Power Limit")
        self.power_apply.clicked.connect(self.apply_power_limit)
        self.power_apply.setEnabled(False)
        power_form.addRow("", self.power_apply)

        layout.addWidget(power_group)

        prime_group = QGroupBox("Graphics Mode")
        prime_layout = QHBoxLayout(prime_group)

        self.prime_combo = QComboBox()
        self.prime_combo.addItems(["intel", "on-demand", "nvidia"])

        self.prime_apply = QPushButton("Apply (reboot required)")
        self.prime_apply.clicked.connect(self.apply_prime_mode)

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
    def _text(value: object, suffix: str = "") -> str:
        if isinstance(value, (int, float)):
            return f"{value:.1f}{suffix}"
        return "N/A"

    def refresh(self) -> None:
        snapshot = self.controller.snapshot()
        gpu = snapshot.get("selected") or {}
        limits = self.controller.get_power_limits()
        mode = snapshot.get("prime")

        if not gpu.get("available"):
            self.temp_card.value_label.setText("--")
            self.usage_card.value_label.setText("--")
            self.power_card.value_label.setText("--")
            self.vram_card.value_label.setText("--")
            self.clock_card.value_label.setText("--")
            self.mode_card.value_label.setText(mode or "N/A")
            reasons = []
            for key in ("nvidia", "intel"):
                info = snapshot.get(key) or {}
                if not info.get("available") and info.get("reason"):
                    reasons.append(str(info["reason"]))
            self.status.setText(
                "No live GPU telemetry source is available."
                + (f" {' '.join(reasons)}" if reasons else "")
            )
            self.power_apply.setEnabled(False)
        else:
            self.temp_card.value_label.setText(
                self._text(gpu.get("temperature"), "°C")
            )
            self.usage_card.value_label.setText(
                self._text(gpu.get("usage"), "%")
            )
            self.power_card.value_label.setText(
                self._text(gpu.get("power"), " W")
            )

            used = gpu.get("memory_used")
            total = gpu.get("memory_total")
            if isinstance(used, (int, float)) and isinstance(total, (int, float)):
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

            vendor = str(gpu.get("vendor", "gpu")).upper()
            self.mode_card.value_label.setText(mode or "N/A")
            self.status.setText(
                f"{gpu.get('name', 'GPU')} detected • {vendor} telemetry"
            )

            if vendor == "NVIDIA" and limits.get("available"):
                minimum = float(limits["minimum"])
                maximum = float(limits["maximum"])
                default = float(limits["default"])
                current = gpu.get("power_limit")

                self.power_spin.setMinimum(minimum)
                self.power_spin.setMaximum(maximum)
                self.power_spin.setValue(
                    float(current)
                    if isinstance(current, (int, float))
                    else default
                )
                self.power_spin.setEnabled(True)
                self.power_apply.setEnabled(True)
                self.default_power.setText(f"{default:.1f} W")
            else:
                self.power_spin.setEnabled(False)
                self.power_apply.setEnabled(False)
                if vendor == "NVIDIA":
                    self.default_power.setText("Unavailable")
                else:
                    self.default_power.setText("NVIDIA only")

        if mode:
            blocked = self.prime_combo.blockSignals(True)
            index = self.prime_combo.findText(mode)
            if index >= 0:
                self.prime_combo.setCurrentIndex(index)
            self.prime_combo.blockSignals(blocked)

    def apply_power_limit(self) -> None:
        watts = self.power_spin.value()
        ok, message = self.controller.set_power_limit(watts)
        if not ok:
            show_error(self, message or "Unable to set GPU power limit.")
            return
        self.status.setText(
            f"GPU power limit requested: {watts:.1f} W."
        )
        self.refresh()

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
            show_error(self, message or "Unable to change PRIME mode.")
            return

        self.status.setText(
            f"PRIME mode set to {mode}. Reboot Ubuntu to activate it."
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
            "Live battery, charging and charge-limit status",
        )
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.capacity_card = metric_card("CHARGE", "--", "Current")
        self.health_card = metric_card("HEALTH", "--", "Full / design")
        self.power_card = metric_card("POWER", "--", "Battery draw")
        self.limit_card = metric_card("LIMIT", "--", "Charge limit")

        cards = QGridLayout()
        cards.addWidget(self.capacity_card, 0, 0)
        cards.addWidget(self.health_card, 0, 1)
        cards.addWidget(self.power_card, 0, 2)
        cards.addWidget(self.limit_card, 1, 0)
        layout.addLayout(cards)

        group = QGroupBox("Charge Limit")
        form = QFormLayout(group)

        self.limit_combo = QComboBox()
        for value in (60, 70, 80, 85, 90, 95, 100):
            self.limit_combo.addItem(f"{value}%")

        self.apply_button = QPushButton("Apply Charge Limit")
        self.apply_button.clicked.connect(self.apply_limit)

        form.addRow("Limit:", self.limit_combo)
        form.addRow("", self.apply_button)
        layout.addWidget(group)

        status_group = QGroupBox("Battery Details")
        status_layout = QVBoxLayout(status_group)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setMinimumHeight(150)
        status_layout.addWidget(self.details)
        layout.addWidget(status_group)

        self.status = QLabel("Reading battery...")
        self.status.setObjectName("info")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        layout.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
        self.refresh()

    @staticmethod
    def _format_minutes(value: object) -> str:
        if not isinstance(value, (int, float)):
            return "N/A"
        total = max(0, int(value))
        hours, minutes = divmod(total, 60)
        return f"{hours}h {minutes}m" if hours else f"{minutes}m"

    def refresh(self) -> None:
        info = self.controller.status()

        if not info.get("available"):
            self.capacity_card.value_label.setText("N/A")
            self.health_card.value_label.setText("N/A")
            self.power_card.value_label.setText("N/A")
            self.limit_card.value_label.setText("Unsupported")
            self.apply_button.setEnabled(False)
            self.details.setPlainText(
                info.get("reason") or "No battery device detected."
            )
            self.status.setText(
                info.get("reason") or "No battery device detected."
            )
            return

        capacity = info.get("capacity")
        health = info.get("health")
        power = info.get("power_w")
        limit = info.get("charge_limit")

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
            f"{limit}%"
            if isinstance(limit, int)
            else "Unsupported"
        )

        if isinstance(limit, int):
            index = self.limit_combo.findText(f"{limit}%")
            if index >= 0:
                blocked = self.limit_combo.blockSignals(True)
                self.limit_combo.setCurrentIndex(index)
                self.limit_combo.blockSignals(blocked)

        supported = bool(info.get("supports_limit"))
        self.apply_button.setEnabled(supported)

        charger = info.get("charger_connected")
        charger_text = (
            "Connected" if charger is True
            else "Disconnected" if charger is False
            else "Unknown"
        )

        voltage = info.get("voltage_v")
        current = info.get("current_a")

        lines = [
            f"Device: {info.get('name', 'Battery')}",
            f"State: {info.get('state') or 'Unknown'}",
            f"Charger: {charger_text}",
            f"Voltage: {voltage:.2f} V" if isinstance(voltage, (int, float)) else "Voltage: N/A",
            f"Current: {current:.2f} A" if isinstance(current, (int, float)) else "Current: N/A",
            f"Time estimate: {self._format_minutes(info.get('time_remaining_minutes'))}",
        ]
        self.details.setPlainText("\n".join(lines))

        self.status.setText(
            "Charge-limit control is supported."
            if supported
            else "Live battery telemetry is available, but this laptop/kernel "
                 "does not expose a writable charge-limit interface."
        )

    def apply_limit(self) -> None:
        value = int(self.limit_combo.currentText().rstrip("%"))
        ok, message = self.controller.set_limit(value)

        if not ok:
            show_error(self, message or "Unable to set battery limit.")
            return

        self.status.setText(
            f"Battery charge limit requested: {value}%."
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


