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
from app.backend.gigactl import GigaCtlController
from app.backend.nvidia import NvidiaController
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
    def __init__(self, performance: PerformanceController, battery: BatteryController,
                 gigactl: GigaCtlController, nvidia: NvidiaController):
        super().__init__()

        self.performance = performance
        self.battery = battery
        self.gigactl = gigactl
        self.nvidia = nvidia
        self.refresh_count = 0

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
        self.timer.start(1500)
        self.refresh()

    def refresh(self) -> None:
        cpu_usage = get_cpu_usage()
        cpu_temp = get_cpu_temperature()
        cpu_freq = get_cpu_frequency()

        if cpu_temp is None:
            self.cpu_card.value_label.setText("--")
        else:
            self.cpu_card.value_label.setText(f"{cpu_temp:.0f}°C")

        ram_percent, used_gb, total_gb = get_ram_usage()
        self.ram_card.value_label.setText(f"{ram_percent:.0f}%")

        gpu = self.nvidia.get_gpu_info()
        if gpu.get("available"):
            self.gpu_card.value_label.setText(
                f"{gpu['temperature']:.0f}°C"
            )
            self.gpu_power_card.value_label.setText(
                f"{gpu['power']:.1f} W"
            )
        else:
            self.gpu_card.value_label.setText("--")
            self.gpu_power_card.value_label.setText("N/A")

        profile = self.performance.current_profile()
        self.profile_card.value_label.setText(
            profile or "Unavailable"
        )

        battery = self.battery.status()
        if battery.get("available") and battery.get("capacity") is not None:
            self.battery_card.value_label.setText(
                f"{battery['capacity']}%"
            )
            self.battery_card.subtitle_label.setText(
                battery.get("state") or "Battery"
            )
        else:
            self.battery_card.value_label.setText("N/A")

        freq_text = f"{cpu_freq / 1000:.2f} GHz" if cpu_freq else "N/A"
        self.snapshot.setText(
            f"CPU usage: {cpu_usage:.0f}%   •   "
            f"CPU frequency: {freq_text}   •   "
            f"RAM: {used_gb:.1f} / {total_gb:.1f} GB   •   "
            f"GPU usage: {gpu.get('usage', 0):.0f}%"
            if gpu.get("available")
            else
            f"CPU usage: {cpu_usage:.0f}%   •   "
            f"CPU frequency: {freq_text}   •   "
            f"RAM: {used_gb:.1f} / {total_gb:.1f} GB   •   "
            f"NVIDIA GPU: unavailable"
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
    def __init__(self, controller: NvidiaController):
        super().__init__()
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(18)

        title, subtitle = page_header(
            "GPU",
            "NVIDIA monitoring, power limit and PRIME mode",
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

        self.default_power = QLabel("--")
        power_form.addRow("Default:", self.default_power)
        power_form.addRow("Requested:", self.power_spin)

        self.power_apply = QPushButton("Apply Power Limit")
        self.power_apply.clicked.connect(self.apply_power_limit)
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

        self.status = QLabel("Reading NVIDIA state...")
        self.status.setObjectName("info")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        layout.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2000)
        self.refresh()

    def refresh(self) -> None:
        gpu = self.controller.get_gpu_info()
        limits = self.controller.get_power_limits()
        mode = self.controller.prime_mode()

        if not gpu.get("available"):
            reason = gpu.get("reason", "NVIDIA GPU unavailable.")
            self.status.setText(reason)
            return

        self.temp_card.value_label.setText(f"{gpu['temperature']:.0f}°C")
        self.usage_card.value_label.setText(f"{gpu['usage']:.0f}%")
        self.power_card.value_label.setText(f"{gpu['power']:.1f} W")
        self.vram_card.value_label.setText(
            f"{gpu['memory_used']:.0f} / {gpu['memory_total']:.0f} MB"
        )
        self.clock_card.value_label.setText(
            f"{gpu['graphics_clock']:.0f} MHz"
        )
        self.mode_card.value_label.setText(mode or "Unknown")

        if limits.get("available"):
            self.power_spin.setMinimum(limits["minimum"])
            self.power_spin.setMaximum(limits["maximum"])
            self.power_spin.setValue(gpu["power_limit"])
            self.default_power.setText(f"{limits['default']:.1f} W")
            self.power_apply.setEnabled(True)
        else:
            self.power_apply.setEnabled(False)
            self.default_power.setText("Unavailable")

        if mode:
            blocked = self.prime_combo.blockSignals(True)
            index = self.prime_combo.findText(mode)
            if index >= 0:
                self.prime_combo.setCurrentIndex(index)
            self.prime_combo.blockSignals(blocked)

        self.status.setText(f"{gpu['name']} detected.")

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
    def __init__(self, controller: GigaCtlController):
        super().__init__()
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(18)

        title, subtitle = page_header(
            "Fans",
            "Manual fan control through the G6 KF gigactl backend",
        )
        layout.addWidget(title)
        layout.addWidget(subtitle)

        controls = QGroupBox("Manual Fan Duty")
        form = QFormLayout(controls)

        self.cpu_slider = QSlider(Qt.Orientation.Horizontal)
        self.cpu_slider.setRange(30, 100)
        self.cpu_slider.setValue(60)

        self.gpu_slider = QSlider(Qt.Orientation.Horizontal)
        self.gpu_slider.setRange(30, 100)
        self.gpu_slider.setValue(60)

        self.cpu_value = QLabel("60%")
        self.gpu_value = QLabel("60%")

        cpu_row = QHBoxLayout()
        cpu_row.addWidget(self.cpu_slider)
        cpu_row.addWidget(self.cpu_value)
        form.addRow("CPU fan:", cpu_row)

        gpu_row = QHBoxLayout()
        gpu_row.addWidget(self.gpu_slider)
        gpu_row.addWidget(self.gpu_value)
        form.addRow("GPU fan:", gpu_row)

        apply_button = QPushButton("Apply Fan Speed")
        apply_button.clicked.connect(self.apply_manual)
        form.addRow("", apply_button)

        auto_button = QPushButton("Return to Firmware Auto")
        auto_button.clicked.connect(self.apply_auto)
        form.addRow("", auto_button)

        layout.addWidget(controls)

        preset_group = QGroupBox("Presets")
        preset_layout = QHBoxLayout(preset_group)

        for label, cpu, gpu in (
            ("Quiet", 45, 45),
            ("Balanced", 60, 60),
            ("Performance", 70, 75),
            ("Max", 100, 100),
        ):
            button = QPushButton(label)
            button.clicked.connect(
                lambda _=False, c=cpu, g=gpu: self.set_preset(c, g)
            )
            preset_layout.addWidget(button)

        layout.addWidget(preset_group)

        status_group = QGroupBox("EC Status")
        status_layout = QVBoxLayout(status_group)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(180)
        status_layout.addWidget(self.output)
        layout.addWidget(status_group)

        self.cpu_slider.valueChanged.connect(
            lambda value: self.cpu_value.setText(f"{value}%")
        )
        self.gpu_slider.valueChanged.connect(
            lambda value: self.gpu_value.setText(f"{value}%")
        )

        self.refresh_button = QPushButton("Refresh Status")
        self.refresh_button.clicked.connect(self.refresh_status)
        layout.addWidget(self.refresh_button, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch()
        self.refresh_status()

    def set_preset(self, cpu: int, gpu: int) -> None:
        self.cpu_slider.setValue(cpu)
        self.gpu_slider.setValue(gpu)
        self.apply_manual()

    def apply_manual(self) -> None:
        result = self.controller.set_fans(
            self.cpu_slider.value(),
            self.gpu_slider.value(),
        )
        if not result.ok:
            show_error(self, result.stderr or "Unable to set fan speed.")
            return
        self.output.setPlainText(result.stdout or "Fan speed applied.")

    def apply_auto(self) -> None:
        result = self.controller.set_fans_auto()
        if not result.ok:
            show_error(self, result.stderr or "Unable to return fan control to auto.")
            return
        self.output.setPlainText(
            result.stdout or "Firmware fan control restored."
        )

    def refresh_status(self) -> None:
        result = self.controller.fan_status()
        self.output.setPlainText(
            result.stdout
            or result.stderr
            or "gigactl is unavailable."
        )


class RGBPage(QWidget):
    def __init__(self, controller: GigaCtlController):
        super().__init__()
        self.controller = controller
        self.selected_color = "#00a2ff"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(18)

        title, subtitle = page_header(
            "RGB Lighting",
            "Single-zone keyboard backlight control",
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
            "Battery health and charge-limit controls",
        )
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.capacity_card = metric_card("CHARGE", "--", "Current")
        self.health_card = metric_card("HEALTH", "--", "Estimated full/design")
        self.limit_card = metric_card("LIMIT", "--", "Charge limit")

        cards = QHBoxLayout()
        cards.addWidget(self.capacity_card)
        cards.addWidget(self.health_card)
        cards.addWidget(self.limit_card)
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

        self.status = QLabel("Reading battery...")
        self.status.setObjectName("info")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        layout.addStretch()
        self.refresh()

    def refresh(self) -> None:
        info = self.controller.status()
        if not info.get("available"):
            self.status.setText("No battery device detected.")
            self.apply_button.setEnabled(False)
            return

        capacity = info.get("capacity")
        health = info.get("health")
        limit = info.get("charge_limit")

        self.capacity_card.value_label.setText(
            f"{capacity}%" if capacity is not None else "N/A"
        )
        self.health_card.value_label.setText(
            f"{health:.0f}%" if health is not None else "N/A"
        )
        self.limit_card.value_label.setText(
            f"{limit}%" if limit is not None else "Unsupported"
        )

        if limit is not None:
            index = self.limit_combo.findText(f"{limit}%")
            if index >= 0:
                self.limit_combo.setCurrentIndex(index)

        supported = self.controller.supports_limit()
        self.apply_button.setEnabled(supported)
        self.status.setText(
            f"{info['name']} • {info.get('state') or 'Unknown state'} • "
            + (
                "Charge limit is supported."
                if supported
                else "Charge limit is not exposed by this laptop/kernel."
            )
        )

    def apply_limit(self) -> None:
        value = int(self.limit_combo.currentText().rstrip("%"))
        ok, message = self.controller.set_limit(value)

        if not ok:
            show_error(self, message or "Unable to set battery limit.")
            return

        self.status.setText(
            f"Battery charge limit set to {value}%. "
            "The firmware may apply the change after a short delay."
        )
        self.refresh()


class SettingsPage(QWidget):
    def __init__(
        self,
        performance: PerformanceController,
        gigactl: GigaCtlController,
        nvidia: NvidiaController,
    ):
        super().__init__()

        system = get_system_info()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(18)

        title, subtitle = page_header(
            "Settings",
            "System information, dependencies and project status",
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

        deps_group = QGroupBox("Backend Availability")
        deps = QFormLayout(deps_group)
        deps.addRow("Power profiles:", QLabel(
            "Available" if performance.available else "Unavailable"
        ))
        deps.addRow("gigactl:", QLabel(
            "Detected" if gigactl.available else "Not detected"
        ))
        deps.addRow("NVIDIA:", QLabel(
            "Detected" if nvidia.command else "nvidia-smi not found"
        ))
        layout.addWidget(deps_group)

        safety = QLabel(
            "Hardware safety: G6-specific EC writes are delegated to gigactl. "
            "This application does not write Gigabyte/Clevo EC registers directly. "
            "CPU/GPU power changes are limited to interfaces exposed by Linux "
            "or NVIDIA and are validated against reported ranges."
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
