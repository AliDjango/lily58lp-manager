"""Qt tray application and service lifecycle."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from qasync import QEventLoop

from .config import Config
from .hid_client import HidClient
from .layout import LayoutMonitor
from .telemetry import collect_report

LOGGER = logging.getLogger(__name__)


class ManagerApplication:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setQuitOnLastWindowClosed(False)
        self.loop = QEventLoop(self.qt_app)
        self.hid = HidClient()
        self.stop_event = asyncio.Event()
        self.pause_event = asyncio.Event()
        self.pause_event.set()
        self.tasks: list[asyncio.Task[None]] = []
        self.shutting_down = False
        self._build_tray()

    @property
    def paused(self) -> bool:
        return not self.pause_event.is_set()

    def _build_icon(self, color: QColor) -> QIcon:
        keyboard_icon = QIcon.fromTheme("input-keyboard")
        pixmap = keyboard_icon.pixmap(64, 64)
        if pixmap.isNull():
            pixmap = QPixmap(64, 64)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(60, 60, 60))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(3, 13, 58, 38, 6, 6)
            painter.setBrush(QColor(230, 230, 230))
            for row in range(2):
                for column in range(6):
                    painter.drawRoundedRect(8 + column * 8, 19 + row * 10, 5, 5, 1, 1)
            painter.end()
        else:
            pixmap = pixmap.copy()

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(36, 36, 28, 28)
        painter.setBrush(color)
        painter.drawEllipse(38, 38, 24, 24)
        painter.end()
        return QIcon(pixmap)

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon()
        self.icon_running = self._build_icon(QColor(0, 200, 0))
        self.icon_paused = self._build_icon(QColor(200, 0, 0))
        self.tray.setIcon(self.icon_running)
        self.tray.setToolTip("Lily58LP Manager — Running")

        menu = QMenu()
        self.status_action = QAction("Running", menu)
        self.status_action.setEnabled(False)
        menu.addAction(self.status_action)
        menu.addSeparator()
        self.pause_action = QAction("Pause HID", menu)
        self.pause_action.triggered.connect(self.toggle_pause)
        menu.addAction(self.pause_action)
        restart_action = QAction("Restart", menu)
        restart_action.triggered.connect(lambda: self._schedule_shutdown(restart=True))
        menu.addAction(restart_action)
        menu.addSeparator()
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self._schedule_shutdown)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.show()

        if not QSystemTrayIcon.isSystemTrayAvailable():
            LOGGER.warning(
                "No system tray is available; the manager will continue in the background"
            )

    def toggle_pause(self) -> None:
        if self.paused:
            self.pause_event.set()
            self.pause_action.setText("Pause HID")
            self.status_action.setText("Running")
            self.tray.setToolTip("Lily58LP Manager — Running")
            self.tray.setIcon(self.icon_running)
        else:
            self.pause_event.clear()
            self.pause_action.setText("Resume HID")
            self.status_action.setText("Paused")
            self.tray.setToolTip("Lily58LP Manager — Paused")
            self.tray.setIcon(self.icon_paused)

    async def _send_layer(self, layer_name: str) -> None:
        await asyncio.to_thread(self.hid.send_layer, layer_name)

    async def _telemetry_loop(self) -> None:
        while not self.stop_event.is_set():
            await self.pause_event.wait()
            try:
                report = await collect_report(self.config)
                await asyncio.to_thread(self.hid.send, report)
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("Telemetry collection failed; retrying next interval")

            try:
                await asyncio.wait_for(
                    self.stop_event.wait(), self.config.telemetry_interval_seconds
                )
            except TimeoutError:
                pass

    def start(self) -> None:
        monitor = LayoutMonitor(
            self.config.persian_layout_index, self._send_layer, lambda: self.paused
        )
        self.tasks = [
            self.loop.create_task(self._telemetry_loop()),
            self.loop.create_task(monitor.run(self.stop_event)),
        ]

    def _schedule_shutdown(self, restart: bool = False) -> None:
        self.loop.create_task(self.shutdown(restart=restart))

    async def shutdown(self, restart: bool = False) -> None:
        if self.shutting_down:
            return
        self.shutting_down = True
        self.stop_event.set()
        self.pause_event.set()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tray.hide()
        self.qt_app.quit()
        self.loop.stop()
        if restart:
            os.execv(sys.executable, [sys.executable, *sys.argv])

    def run(self) -> int:
        asyncio.set_event_loop(self.loop)
        self.start()
        signal.signal(signal.SIGTERM, lambda *_: self._schedule_shutdown())
        signal.signal(signal.SIGINT, lambda *_: self._schedule_shutdown())
        with self.loop:
            self.loop.run_forever()
        return 0


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LILY58_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return ManagerApplication(Config.load()).run()
