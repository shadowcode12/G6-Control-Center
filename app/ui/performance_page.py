from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.backend.performance import PerformanceController


class PerformancePage(QWidget):
    profile_changed = Signal(str)

    def __init__(self, controller: PerformanceController | None = None):
        super().__init__()

        self.controller = controller or PerformanceController()
        self.profile_buttons: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        title = QLabel("Performance")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "System power profiles and CPU performance controls"
        )
        subtitle.setObjectName("subtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        profile_group = QGroupBox("Power Profile")
        profile_layout = QGridLayout(profile_group)
        profile_layout.setHorizontalSpacing(12)
        profile_layout.setVerticalSpacing(12)

        profiles = [
            ("silent", "Silent"),
            ("balanced", "Balanced"),
            ("performance", "Performance"),
            ("gaming", "Gaming"),
        ]

        for index, (key, label) in enumerate(profiles):
            button = QPushButton(label)
            button.setObjectName("profileButton")
            button.setMinimumHeight(52)
            button.clicked.connect(
                lambda _checked=False, value=key: self.select_profile(value)
            )

            self.profile_buttons[key] = button
            profile_layout.addWidget(button, index // 2, index % 2)

        layout.addWidget(profile_group)

        status_group = QGroupBox("Current CPU State")
        status_layout = QVBoxLayout(status_group)
        status_layout.setSpacing(10)

        self.profile_label = QLabel("Current profile: --")
        self.driver_label = QLabel("CPU driver: --")
        self.epp_label = QLabel("Energy preference: --")
        self.turbo_label = QLabel("Turbo Boost: --")

        for label in (
            self.profile_label,
            self.driver_label,
            self.epp_label,
            self.turbo_label,
        ):
            label.setObjectName("metricLabel")
            status_layout.addWidget(label)

        layout.addWidget(status_group)

        actions = QHBoxLayout()

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_state)

        self.turbo_button = QPushButton("Turbo")
        self.turbo_button.clicked.connect(self.toggle_turbo)

        actions.addWidget(self.refresh_button)
        actions.addWidget(self.turbo_button)
        actions.addStretch()

        layout.addLayout(actions)
        layout.addStretch()

        self.refresh_state()

    def select_profile(self, profile: str) -> None:
        result = self.controller.set_profile(profile)

        if result.ok:
            self.profile_changed.emit(profile)
            self.refresh_state()
        else:
            self.profile_label.setText(
                f"Profile change failed: {result.stderr or 'unknown error'}"
            )

    def toggle_turbo(self) -> None:
        current = self.controller.turbo_enabled()
        if current is None:
            self.turbo_label.setText("Turbo Boost: unsupported")
            return

        result = self.controller.set_turbo_enabled(not current)

        if result.ok:
            self.refresh_state()
        else:
            self.turbo_label.setText(
                f"Turbo change failed: {result.stderr or 'unknown error'}"
            )

    def refresh_state(self) -> None:
        current = self.controller.current_profile()
        driver = self.controller.cpu_driver()
        epp = self.controller.energy_performance_preference()
        turbo = self.controller.turbo_enabled()

        self.profile_label.setText(
            f"Current profile: {current or 'unavailable'}"
        )
        self.driver_label.setText(
            f"CPU driver: {driver or 'unavailable'}"
        )
        self.epp_label.setText(
            f"Energy preference: {epp or 'unavailable'}"
        )

        if turbo is None:
            turbo_text = "unsupported"
        else:
            turbo_text = "ON" if turbo else "OFF"

        self.turbo_label.setText(f"Turbo Boost: {turbo_text}")

        available = set(self.controller.available_profiles())

        for key, button in self.profile_buttons.items():
            target = self.controller.PROFILE_ALIASES[key]
            button.setEnabled(target in available)

        self.turbo_button.setEnabled(turbo is not None)
