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
from app.backend.cpu import CpuController
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
            "System-wide profiles for everyday use, work and gaming",
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

        note = QLabel(
            "Performance profiles change the standard Linux system power profile. "
            "CPU-specific controls live on the dedicated CPU page."
        )
        note.setObjectName("info")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.status = QLabel("Ready")
        self.status.setObjectName("info")
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

    def refresh_state(self) -> None:
        available = set(self.controller.available_profiles())
        for key, button in self.profile_buttons.items():
            button.setEnabled(
                self.controller.PROFILE_ALIASES[key] in available
            )

        current = self.controller.current_profile()
        self.status.setText(
            f"Current Linux profile: {current or 'Unavailable'}"
        )


class CPUPage(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(18)

        title, subtitle = page_header(
            "CPU",
            "Live CPU telemetry, Turbo, EPP and optional RAPL controls",
        )
        layout.addWidget(title)
        layout.addWidget(subtitle)

        cards = QGridLayout()
        self.usage_card = metric_card("CPU USAGE", "--", "All cores")
        self.temp_card = metric_card("TEMPERATURE", "--", "CPU")
        self.freq_card = metric_card("FREQUENCY", "--", "Average")
        self.power_card = metric_card("PACKAGE POWER", "--", "RAPL")

        cards.addWidget(self.usage_card, 0, 0)
        cards.addWidget(self.temp_card, 0, 1)
        cards.addWidget(self.freq_card, 0, 2)
        cards.addWidget(self.power_card, 1, 0)
        layout.addLayout(cards)

        control_group = QGroupBox("CPU Controls")
        control_form = QFormLayout(control_group)

        self.driver_label = QLabel("--")
        self.turbo_label = QLabel("--")
        self.turbo_button = QPushButton("Toggle Turbo")
        self.turbo_button.clicked.connect(self.toggle_turbo)

        self.epp_combo = QComboBox()
        for key in self.controller.EPP_OPTIONS:
            self.epp_combo.addItem(
                self.controller.EPP_LABELS[key],
                key,
            )

        self.epp_apply = QPushButton("Apply")
        self.epp_apply.clicked.connect(
            lambda: self.apply_epp(self.epp_combo.currentData())
        )

        control_form.addRow("CPU driver:", self.driver_label)
        turbo_row = QHBoxLayout()
        turbo_row.addWidget(self.turbo_label)
        turbo_row.addWidget(self.turbo_button)
        control_form.addRow("Turbo Boost:", turbo_row)

        epp_row = QHBoxLayout()
        epp_row.addWidget(self.epp_combo)
        epp_row.addWidget(self.epp_apply)
        control_form.addRow("Energy Preference:", epp_row)

        layout.addWidget(control_group)

        self.rapl_group = QGroupBox("Intel RAPL Presets")
        self.rapl_form = QFormLayout(self.rapl_group)
        self.rapl_status = QLabel("Checking kernel RAPL support...")
        self.rapl_status.setWordWrap(True)
        self.rapl_form.addRow("Status:", self.rapl_status)

        self.rapl_current = QLabel("--")
        self.rapl_range = QLabel("--")
        self.rapl_form.addRow("Current:", self.rapl_current)
        self.rapl_form.addRow("Kernel range:", self.rapl_range)

        button_row = QHBoxLayout()
        self.rapl_buttons: dict[str, QPushButton] = {}
        for key, label in (
            ("low", "Low"),
            ("mid", "Balanced"),
            ("high", "High"),
        ):
            button = QPushButton(label)
            button.clicked.connect(
                lambda _=False, value=key: self.apply_rapl(value)
            )
            self.rapl_buttons[key] = button
            button_row.addWidget(button)

        self.rapl_form.addRow("Preset:", button_row)
        layout.addWidget(self.rapl_group)

        note = QLabel(
            "RAPL controls are shown only when the Linux kernel exposes PL1/PL2. "
            "Preset values are clamped to the live kernel range. "
            "No arbitrary voltage or overclock controls are provided."
        )
        note.setObjectName("info")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.status = QLabel("Reading CPU...")
        self.status.setObjectName("info")
        layout.addWidget(self.status)

        layout.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
        self.refresh()

    def refresh(self) -> None:
        info = self.controller.telemetry()

        usage = get_cpu_usage()

        self.usage_card.value_label.setText(
            f"{usage:.0f}%"
        )
        temp = info.get("temperature")
        self.temp_card.value_label.setText(
            f"{temp:.0f}°C"
            if isinstance(temp, (int, float))
            else "N/A"
        )

        freq = info.get("frequency_mhz")
        self.freq_card.value_label.setText(
            f"{freq:.0f} MHz"
            if isinstance(freq, (int, float))
            else "N/A"
        )

        package_power = info.get("package_power_w")
        self.power_card.value_label.setText(
            f"{package_power:.1f} W"
            if isinstance(package_power, (int, float))
            else "N/A"
        )

        self.driver_label.setText(
            info.get("driver") or "Unavailable"
        )

        turbo = info.get("turbo")
        self.turbo_label.setText(
            "ON" if turbo is True
            else "OFF" if turbo is False
            else "Unavailable"
        )
        self.turbo_button.setEnabled(turbo is not None)

        epp = info.get("epp")
        if epp:
            blocked = self.epp_combo.blockSignals(True)
            index = self.epp_combo.findData(epp)
            if index >= 0:
                self.epp_combo.setCurrentIndex(index)
            self.epp_combo.blockSignals(blocked)

        constraints = info.get("rapl") or []
        by_index = {item.index: item for item in constraints}
        if 0 in by_index and 1 in by_index:
            pl1 = by_index[0]
            pl2 = by_index[1]
            self.rapl_status.setText(
                "Supported: kernel exposes PL1 and PL2."
            )
            self.rapl_current.setText(
                f"PL1 {pl1.current_watts:.1f} W • "
                f"PL2 {pl2.current_watts:.1f} W"
            )

            ranges = []
            for item in (pl1, pl2):
                if (
                    item.minimum_watts is not None
                    and item.maximum_watts is not None
                ):
                    ranges.append(
                        f"PL{item.index + 1}: "
                        f"{item.minimum_watts:.1f}-{item.maximum_watts:.1f} W"
                    )
                else:
                    ranges.append(
                        f"PL{item.index + 1}: range unavailable"
                    )

            self.rapl_range.setText(" • ".join(ranges))

            preset_available = any(
                item.minimum_watts is not None
                and item.maximum_watts is not None
                for item in (pl1, pl2)
            )
            for button in self.rapl_buttons.values():
                button.setEnabled(preset_available)
        else:
            self.rapl_status.setText(
                "Not exposed by the current Linux kernel/firmware."
            )
            self.rapl_current.setText("--")
            self.rapl_range.setText("--")
            for button in self.rapl_buttons.values():
                button.setEnabled(False)

        self.status.setText(
            f"{info.get('driver') or 'CPU'} telemetry • live"
        )

    def toggle_turbo(self) -> None:
        current = self.controller.turbo_enabled()
        if current is None:
            show_error(
                self,
                "Turbo Boost control is not exposed by this kernel.",
            )
            return

        result = self.controller.set_turbo_enabled(not current)
        if not result.ok:
            show_error(
                self,
                result.stderr or "Unable to change Turbo Boost.",
            )
            return

        self.refresh()

    def apply_epp(self, value: str | None) -> None:
        if not value:
            return

        result = self.controller.set_energy_preference(value)
        if not result.ok:
            show_error(
                self,
                result.stderr or "Unable to change Energy Preference.",
            )
            return

        self.refresh()

    def apply_rapl(self, preset: str) -> None:
        result = self.controller.set_rapl_preset(preset)
        if not result.ok:
            show_error(
                self,
                result.stderr or "Unable to apply RAPL preset.",
            )
            return

        self.status.setText(
            f"RAPL {preset.title()} preset applied."
        )
        self.refresh()


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
            "Live fan RPM with paired thermal speed profiles",
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

        control_group = QGroupBox("Fan Speed")
        controls = QHBoxLayout(control_group)

        self.mode_buttons: dict[str, QPushButton] = {}
        for mode, label in (
            ("quiet", "Quiet"),
            ("balanced", "Balanced"),
            ("high", "High"),
            ("automatic", "Automatic"),
        ):
            button = QPushButton(label)
            button.setObjectName("profileButton")
            button.setMinimumHeight(48)
            button.clicked.connect(
                lambda _=False, value=mode: self.set_mode(value)
            )
            self.mode_buttons[mode] = button
            controls.addWidget(button)

        layout.addWidget(control_group)

        self.control_note = QLabel(
            "Fan profiles are paired: both physical fans are controlled together. "
            "Independent CPU/GPU fan control is not exposed. Automatic returns "
            "thermal control to the firmware."
        )
        self.control_note.setObjectName("info")
        self.control_note.setWordWrap(True)
        layout.addWidget(self.control_note)

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

    def set_mode(self, mode: str) -> None:
        ok, message = self.controller.set_mode(mode)
        if not ok:
            show_error(
                self,
                message or "Unable to change fan speed mode.",
            )
            return

        self.refresh_status()

    def refresh_status(self) -> None:
        info = self.controller.status()
        fans = info.get("fans") or []

        if len(fans) >= 1:
            fan = fans[0]
            rpm = fan.get("rpm")
            duty = fan.get("duty_percent")
            self.cpu_fan_card.value_label.setText(
                f"{int(rpm)}"
                if isinstance(rpm, (int, float))
                else "N/A"
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
                f"{int(rpm)}"
                if isinstance(rpm, (int, float))
                else "N/A"
            )
            self.gpu_duty_card.value_label.setText(
                f"{int(duty)}%"
                if isinstance(duty, (int, float))
                else "N/A"
            )
        else:
            self.gpu_fan_card.value_label.setText("N/A")
            self.gpu_duty_card.value_label.setText("N/A")

        mode = info.get("mode", "automatic")
        for key, button in self.mode_buttons.items():
            button.setEnabled(info.get("available", False) or key == "automatic")
            button.setProperty("active", key == mode)
            button.style().unpolish(button)
            button.style().polish(button)

        if info.get("available"):
            source = info.get("source", "native")
            self.output.setPlainText(
                f"Source: {source}\n"
                f"EC telemetry: live\n"
                f"Current mode: {mode.title()}\n"
                f"Independent fan control: disabled"
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
        state = self.controller.state()

        self.selected_color = self._rgb_hex(
            state["r"],
            state["g"],
            state["b"],
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(18)

        title, subtitle = page_header(
            "RGB Lighting",
            "Single-zone keyboard lighting for the Gigabyte G6 KF",
        )
        layout.addWidget(title)
        layout.addWidget(subtitle)

        preview_group = QGroupBox("Keyboard Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.keyboard_frame = QFrame()
        self.keyboard_frame.setObjectName("keyboardFrame")
        keyboard_layout = QHBoxLayout(self.keyboard_frame)
        keyboard_layout.setContentsMargins(14, 14, 14, 14)
        keyboard_layout.setSpacing(10)

        self.key_widgets: list[QPushButton] = []
        self._build_keyboard_layout(keyboard_layout)

        preview_layout.addWidget(self.keyboard_frame)
        layout.addWidget(preview_group)

        color_group = QGroupBox("Color")
        color_layout = QHBoxLayout(color_group)

        self.color_preview = QFrame()
        self.color_preview.setFixedSize(52, 52)

        self.hex_label = QLabel(self.selected_color.upper())
        self.hex_label.setMinimumWidth(90)

        choose_button = QPushButton("Choose Color")
        choose_button.clicked.connect(self.choose_color)

        color_layout.addWidget(self.color_preview)
        color_layout.addWidget(self.hex_label)
        color_layout.addWidget(choose_button)
        color_layout.addStretch()

        layout.addWidget(color_group)

        presets_group = QGroupBox("Presets")
        presets = QGridLayout(presets_group)

        for index, (name, rgb) in enumerate(
            self.controller.PRESETS.items()
        ):
            button = QPushButton(name)
            button.clicked.connect(
                lambda _=False, value=rgb: self.set_rgb(*value)
            )
            button.setMinimumHeight(40)
            presets.addWidget(
                button,
                index // 5,
                index % 5,
            )

        layout.addWidget(presets_group)

        brightness_group = QGroupBox("Brightness")
        brightness_layout = QHBoxLayout(brightness_group)

        self.brightness = QSlider(Qt.Orientation.Horizontal)
        self.brightness.setRange(0, 100)
        self.brightness.setValue(state["brightness"])

        self.brightness_label = QLabel(f"{state['brightness']}%")
        self.brightness.valueChanged.connect(
            lambda value: self.brightness_label.setText(f"{value}%")
        )

        brightness_apply = QPushButton("Apply")
        brightness_apply.clicked.connect(self.apply_brightness)

        brightness_layout.addWidget(self.brightness)
        brightness_layout.addWidget(self.brightness_label)
        brightness_layout.addWidget(brightness_apply)

        layout.addWidget(brightness_group)

        actions_group = QGroupBox("Keyboard")
        actions = QHBoxLayout(actions_group)

        self.power_button = QPushButton(
            "Turn OFF" if state["enabled"] else "Turn ON"
        )
        self.power_button.clicked.connect(self.toggle_keyboard)

        apply_color = QPushButton("Apply Color")
        apply_color.clicked.connect(self.apply_color)

        actions.addWidget(apply_color)
        actions.addWidget(self.power_button)
        actions.addStretch()

        layout.addWidget(actions_group)

        self.status = QLabel(
            "Native RGB backend ready."
            if self.controller.available
            else "Native RGB backend is not available."
        )
        self.status.setObjectName("info")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        layout.addStretch()

        self.refresh_status()

    @staticmethod
    def _rgb_hex(r: int, g: int, b: int) -> str:
        return f"#{r:02x}{g:02x}{b:02x}"

    def _build_keyboard_layout(self, parent: QHBoxLayout) -> None:
        main = QVBoxLayout()
        main.setSpacing(4)

        rows = [
            ["Esc", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"],
            ["~", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=", "Backspace"],
            ["Tab", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "[", "]", "\\", "Ins"],
            ["Caps", "A", "S", "D", "F", "G", "H", "J", "K", "L", ";", "'", "Enter"],
            ["Shift", "Z", "X", "C", "V", "B", "N", "M", ",", ".", "/", "Shift"],
            ["Ctrl", "Fn", "Win", "Alt", "Space", "Alt", "Menu", "Ctrl", "←", "↓", "↑", "→"],
        ]

        for labels in rows:
            row = QHBoxLayout()
            row.setSpacing(3)
            for label in labels:
                key = QPushButton(label)
                key.setEnabled(False)
                key.setFixedHeight(28)
                key.setMinimumWidth(24)
                stretch = 2 if label in {
                    "Backspace", "Enter", "Shift", "Tab", "Caps", "Space"
                } else 1
                row.addWidget(key, stretch)
                self.key_widgets.append(key)
            main.addLayout(row)

        parent.addLayout(main, 5)

        numpad = QGridLayout()
        numpad.setHorizontalSpacing(3)
        numpad.setVerticalSpacing(3)

        cells = [
            ("Num", 0, 0, 1, 1),
            ("/", 0, 1, 1, 1),
            ("*", 0, 2, 1, 1),
            ("-", 0, 3, 1, 1),
            ("7", 1, 0, 1, 1),
            ("8", 1, 1, 1, 1),
            ("9", 1, 2, 1, 1),
            ("+", 1, 3, 2, 1),
            ("4", 2, 0, 1, 1),
            ("5", 2, 1, 1, 1),
            ("6", 2, 2, 1, 1),
            ("1", 3, 0, 1, 1),
            ("2", 3, 1, 1, 1),
            ("3", 3, 2, 1, 1),
            ("Enter", 3, 3, 2, 1),
            ("0", 5, 0, 1, 2),
            (".", 5, 2, 1, 1),
        ]

        for label, row_index, column, row_span, column_span in cells:
            key = QPushButton(label)
            key.setEnabled(False)
            key.setFixedHeight(28)
            numpad.addWidget(
                key,
                row_index,
                column,
                row_span,
                column_span,
            )
            self.key_widgets.append(key)

        parent.addLayout(numpad, 1)
        self._refresh_key_styles()

    def _refresh_key_styles(self) -> None:
        color = self.selected_color
        for key in self.key_widgets:
            key.setStyleSheet(
                f"""
                QPushButton {{
                    background: #171c26;
                    border: 1px solid #303747;
                    border-radius: 5px;
                    color: #cfd5df;
                    padding: 4px 6px;
                }}
                QPushButton:disabled {{
                    background: {color};
                    color: white;
                    border: 1px solid {color};
                }}
                """
            )

        self.color_preview.setStyleSheet(
            f"QFrame {{
                background: {color};
                border-radius: 10px;
                border: 1px solid {color};
            }}"
        )
        self.hex_label.setText(color.upper())

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
        self._refresh_key_styles()

    def set_rgb(self, r: int, g: int, b: int) -> None:
        self.set_color(self._rgb_hex(r, g, b))
        self.apply_color()

    def _selected_rgb(self) -> tuple[int, int, int]:
        value = self.selected_color.lstrip("#")
        return (
            int(value[0:2], 16),
            int(value[2:4], 16),
            int(value[4:6], 16),
        )

    def apply_color(self) -> None:
        r, g, b = self._selected_rgb()
        ok, message = self.controller.set_color(r, g, b)

        if not ok:
            self.status.setText(
                message or "Unable to apply keyboard color."
            )
            return

        self.status.setText(
            f"Keyboard color applied: {self.selected_color.upper()}"
        )
        self.refresh_status()

    def apply_brightness(self) -> None:
        ok, message = self.controller.set_brightness(
            self.brightness.value()
        )
        if not ok:
            self.status.setText(
                message or "Unable to apply keyboard brightness."
            )
            return

        self.status.setText(
            f"Keyboard brightness: {self.brightness.value()}%"
        )
        self.refresh_status()

    def toggle_keyboard(self) -> None:
        state = self.controller.state()
        enabled = not state["enabled"]
        ok, message = self.controller.set_enabled(enabled)

        if not ok:
            self.status.setText(
                message or "Unable to change keyboard state."
            )
            return

        self.status.setText(
            "Keyboard backlight ON."
            if enabled
            else "Keyboard backlight OFF."
        )
        self.refresh_status()

    def refresh_status(self) -> None:
        state = self.controller.state()

        self.selected_color = self._rgb_hex(
            state["r"],
            state["g"],
            state["b"],
        )
        self.brightness.setValue(state["brightness"])
        self.brightness_label.setText(f"{state['brightness']}%")
        self.power_button.setText(
            "Turn OFF" if state["enabled"] else "Turn ON"
        )
        self._refresh_key_styles()

        if state["available"]:
            self.status.setText(
                f"1-zone RGB • {self.selected_color.upper()} • "
                f"{state['brightness']}% • "
                f"{'ON' if state['enabled'] else 'OFF'}"
            )
        else:
            self.status.setText(
                "Native RGB backend unavailable. "
                "Load ec_sys with write support and use the verified G6 KF hardware."
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
            "Live battery health, charging state and charge protection",
        )
        layout.addWidget(title)
        layout.addWidget(subtitle)

        cards = QGridLayout()
        cards.setHorizontalSpacing(14)
        cards.setVerticalSpacing(14)

        self.capacity_card = metric_card("CHARGE", "--", "Current")
        self.health_card = metric_card("HEALTH", "--", "Full / design")
        self.power_card = metric_card("POWER", "--", "Battery draw")
        self.state_card = metric_card("STATE", "--", "Charging state")

        cards.addWidget(self.capacity_card, 0, 0)
        cards.addWidget(self.health_card, 0, 1)
        cards.addWidget(self.power_card, 0, 2)
        cards.addWidget(self.state_card, 1, 0)

        layout.addLayout(cards)

        charge_group = QGroupBox("Charging Protection")
        charge_form = QFormLayout(charge_group)

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

        self.start_label = QLabel("Start charging below:")
        self.stop_label = QLabel("Stop charging at:")

        self.apply_button = QPushButton("Apply Charging Mode")
        self.apply_button.clicked.connect(self.apply_mode)

        charge_form.addRow("Mode:", self.mode_combo)
        charge_form.addRow(self.start_label, self.start_combo)
        charge_form.addRow(self.stop_label, self.stop_combo)
        charge_form.addRow("", self.apply_button)

        self.capability_label = QLabel("Checking charge-control support...")
        self.capability_label.setObjectName("info")
        self.capability_label.setWordWrap(True)
        charge_form.addRow("", self.capability_label)

        layout.addWidget(charge_group)

        detail_group = QGroupBox("Battery Details")
        detail_layout = QGridLayout(detail_group)

        self.state_value = QLabel("--")
        self.charger_value = QLabel("--")
        self.driver_value = QLabel("--")
        self.voltage_value = QLabel("--")
        self.current_value = QLabel("--")
        self.eta_value = QLabel("--")

        detail_layout.addWidget(QLabel("State"), 0, 0)
        detail_layout.addWidget(self.state_value, 0, 1)
        detail_layout.addWidget(QLabel("Charger"), 0, 2)
        detail_layout.addWidget(self.charger_value, 0, 3)

        detail_layout.addWidget(QLabel("Driver"), 1, 0)
        detail_layout.addWidget(self.driver_value, 1, 1)
        detail_layout.addWidget(QLabel("Voltage"), 1, 2)
        detail_layout.addWidget(self.voltage_value, 1, 3)

        detail_layout.addWidget(QLabel("Current"), 2, 0)
        detail_layout.addWidget(self.current_value, 2, 1)
        detail_layout.addWidget(QLabel("Time estimate"), 2, 2)
        detail_layout.addWidget(self.eta_value, 2, 3)

        layout.addWidget(detail_group)

        self.status = QLabel("Reading battery...")
        self.status.setObjectName("info")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        layout.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)

        self._update_custom_visibility("Full Charge")
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
            for card in (
                self.capacity_card,
                self.health_card,
                self.power_card,
                self.state_card,
            ):
                card.value_label.setText("N/A")

            self.mode_combo.setEnabled(False)
            self.start_combo.setEnabled(False)
            self.stop_combo.setEnabled(False)
            self.apply_button.setEnabled(False)
            self.capability_label.setText(
                info.get("reason")
                or "Battery telemetry is unavailable."
            )
            self.status.setText(
                info.get("reason")
                or "Battery telemetry is unavailable."
            )
            return

        capacity = info.get("capacity")
        health = info.get("health")
        power = info.get("power_w")
        state = info.get("state") or "Unknown"

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
        self.state_card.value_label.setText(state.title())

        self.state_value.setText(state.title())
        charger = info.get("charger_connected")
        self.charger_value.setText(
            "Connected"
            if charger is True
            else "Disconnected"
            if charger is False
            else "Unknown"
        )
        self.driver_value.setText(
            info.get("driver") or "Kernel default"
        )

        voltage = info.get("voltage_v")
        current = info.get("current_a")

        self.voltage_value.setText(
            f"{voltage:.2f} V"
            if isinstance(voltage, (int, float))
            else "N/A"
        )
        self.current_value.setText(
            f"{current:.2f} A"
            if isinstance(current, (int, float))
            else "N/A"
        )
        self.eta_value.setText(
            self._format_minutes(
                info.get("time_remaining_minutes")
            )
        )

        start = info.get("charge_start")
        stop = info.get("charge_limit")

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

        self.mode_combo.setEnabled(supports_end)
        self.start_combo.setEnabled(supports_custom)
        self.stop_combo.setEnabled(supports_custom)
        self.apply_button.setEnabled(supports_end)

        if supports_end:
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

            self.capability_label.setText(
                "Charge protection is available through the active Linux "
                "battery driver."
            )
        else:
            blocked = self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentText("Full Charge")
            self.mode_combo.blockSignals(blocked)
            self._update_custom_visibility("Full Charge")
            self.capability_label.setText(
                "Battery telemetry is live, but the active Linux battery "
                "driver is not exposing writable charge thresholds. "
                "The controls remain disabled rather than pretending they work."
            )

        self.status.setText(
            f"Battery telemetry • {state.title()} • live"
        )

    def apply_mode(self) -> None:
        mode = self.mode_combo.currentText()

        if mode == "Full Charge":
            ok, message = self.controller.set_full_charge()
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
            self.status.setText(
                message or "Unable to apply charging mode."
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
            "telemetry service. CPU power-limit, GPU power-limit, "
            "overclocking and undervolting controls are intentionally not exposed."
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


