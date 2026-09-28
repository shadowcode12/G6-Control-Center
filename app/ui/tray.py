from __future__ import annotations

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from app.backend.performance import PerformanceController


class TrayController:
    """Optional system-tray profile switcher.

    Some GNOME installations do not display legacy tray icons. The main window
    remains the primary UI when the tray is unavailable.
    """

    def __init__(self, window: QWidget, performance: PerformanceController):
        self.window = window
        self.performance = performance
        self.tray = QSystemTrayIcon(self._icon(), window)
        self.tray.setToolTip("G6 Control Center")

        menu = QMenu()
        show = QAction("Open G6 Control Center", menu)
        show.triggered.connect(self.window.showNormal)
        show.triggered.connect(self.window.raise_)
        show.triggered.connect(self.window.activateWindow)
        menu.addAction(show)
        menu.addSeparator()

        for key, label in (
            ("silent", "Silent"),
            ("balanced", "Balanced"),
            ("performance", "Performance"),
            ("gaming", "Gaming"),
        ):
            action = QAction(label, menu)
            action.triggered.connect(
                lambda _checked=False, value=key: self.set_profile(value)
            )
            menu.addAction(action)

        menu.addSeparator()
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.window.close)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._activated)

    @staticmethod
    def _icon() -> QIcon:
        icon = QIcon.fromTheme("g6-control-center")
        return icon

    def show(self) -> bool:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return False
        self.tray.show()
        return True

    def set_profile(self, profile: str) -> None:
        result = self.performance.set_profile(profile)
        if result.ok:
            self.tray.showMessage(
                "G6 Control Center",
                f"{profile.title()} profile selected.",
                QSystemTrayIcon.MessageIcon.Information,
                1800,
            )
        else:
            self.tray.showMessage(
                "G6 Control Center",
                result.stderr or "Could not change profile.",
                QSystemTrayIcon.MessageIcon.Warning,
                2500,
            )

    def _activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.window.showNormal()
            self.window.raise_()
            self.window.activateWindow()
