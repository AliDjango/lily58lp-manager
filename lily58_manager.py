#!/usr/bin/env python3

import hid
import asyncio
import psutil
import struct
import sys
import signal
import os
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor
from PyQt6.QtCore import QTimer, Qt
import requests
from dbus_next.aio import MessageBus
from dbus_next import BusType

# ---------- Lily58 HID Config ----------
VENDOR_ID     = 0x1209
PRODUCT_ID    = 0x5800
USAGE_PAGE    = 0xFF60
USAGE         = 0x61
REPORT_LENGTH = 32

PERSIAN_INDEX = 1  # KDE layout index for Persian

# ---------- HID Functions ----------
def get_raw_hid_interface():
    devices = hid.enumerate(VENDOR_ID, PRODUCT_ID)
    raw_hid_interfaces = [d for d in devices if d['usage_page'] == USAGE_PAGE and d['usage'] == USAGE]
    if not raw_hid_interfaces:
        print("No device found")
        return None
    interface = hid.Device(path=raw_hid_interfaces[0]['path'])
    return interface

def send_raw_report(data_bytes):
    interface = get_raw_hid_interface()
    if interface is None:
        return
    report = [0x85] + list(data_bytes)
    report += [0x00] * (REPORT_LENGTH - len(report))
    report_bytes = bytes(report)
    try:
        interface.write(report_bytes)
    except Exception as e:
        print(f"Error writing HID report: {e}")
    finally:
        interface.close()

def send_layer_command(layer_name: str):
    print(f"Switching to {layer_name}")
    data = [ord(c) for c in layer_name]
    send_raw_report(data)

# ---------- System Info ----------
def get_system_status():
    """Returns system_status_t fields as bytes."""
    cpu_temp = get_cpu_temp()
    cpu_percent = int(psutil.cpu_percent(interval=0.2))
    gpu_temp = 0
    gpu_percent = 0
    ram_usage = int(round((psutil.virtual_memory().total - psutil.virtual_memory().available) / 1024 / 1024 / 1024,0))
    ram_percent = int(psutil.virtual_memory().percent * 10)
    vram_usage = 0
    vram_percent = 0
    try:
        room_temp_1 = int(float(requests.get("http://192.168.1.200:9090/api/v1/query?query=temperature").json()['data']['result'][0]['value'][1])*10)
    except Exception:
        room_temp_1 = 0
    try:
        room_temp_2 = int(float(requests.get("http://192.168.1.200:9090/api/v1/query?query=thermometer_temperature_celsius").json()['data']['result'][0]['value'][1])*10)
    except Exception:
        room_temp_2 = 0

    packed = struct.pack("<BBBBHHHHHH", cpu_temp,cpu_percent,gpu_temp,gpu_percent,ram_usage,ram_percent,vram_usage,vram_percent,room_temp_1,room_temp_2)
    return packed

def get_cpu_temp():
    temps = psutil.sensors_temperatures()
    if "coretemp" in temps:
        return int(sum(t.current for t in temps["coretemp"]) / len(temps["coretemp"]))
    elif "cpu_thermal" in temps:
        return int(temps["cpu_thermal"][0].current)
    return 0

# ---------- Async Task Manager ----------
class AsyncTaskManager:
    def __init__(self):
        self.loop = None
        self.tasks = []
        self.running = False
        self.paused = False

    def start(self):
        self.running = True
        self.paused = False
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.tasks = [
            self.loop.create_task(self.monitor_kde_layout()),
            self.loop.create_task(self.system_telemetry_task())
        ]

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def stop(self):
        self.running = False
        if self.loop and self.tasks:
            for task in self.tasks:
                task.cancel()
            self.loop.run_until_complete(asyncio.gather(*self.tasks, return_exceptions=True))
            self.loop.close()

    def process_events(self):
        if self.loop and self.running:
            self.loop.call_soon(self.loop.stop)
            self.loop.run_forever()

    async def monitor_kde_layout(self):
        try:
            bus = await MessageBus(bus_type=BusType.SESSION).connect()
            introspection = await bus.introspect('org.kde.keyboard', '/Layouts')
            obj = bus.get_proxy_object('org.kde.keyboard', '/Layouts', introspection)
            iface = obj.get_interface('org.kde.KeyboardLayouts')

            current_index = await iface.call_get_layout()
            if current_index == PERSIAN_INDEX:
                send_layer_command("QWERTY")
            else:
                send_layer_command("DVORAK")

            def layout_changed_handler(index):
                if not self.paused:
                    if index == PERSIAN_INDEX:
                        send_layer_command("QWERTY")
                    else:
                        send_layer_command("DVORAK")

            iface.on_layout_changed(layout_changed_handler)
            print("Listening for layout changes...")

            while self.running:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            print("Layout monitor stopped")
        except Exception as e:
            print(f"Error in layout monitor: {e}")

    async def system_telemetry_task(self):
        try:
            print("Sending system telemetry...")
            while self.running:
                if not self.paused:
                    status = get_system_status()
                    send_raw_report(status)
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            print("Telemetry task stopped")
        except Exception as e:
            print(f"Error in telemetry: {e}")

# ---------- System Tray Application ----------
class TrayApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # Create system tray icon
        self.tray = QSystemTrayIcon()
        self.tray.setToolTip("Lily58 HID Manager")

        # Create icons from theme with color overlay
        self.icon_green = self.create_colored_theme_icon(QColor(0, 200, 0))  # Green
        self.icon_red = self.create_colored_theme_icon(QColor(200, 0, 0))    # Red

        # Set initial icon to green
        self.tray.setIcon(self.icon_green)

        # Create menu
        menu = QMenu()

        self.status_action = QAction("Running", menu)
        self.status_action.setEnabled(False)
        menu.addAction(self.status_action)

        menu.addSeparator()

        self.pause_action = QAction("Pause HID", menu)
        self.pause_action.triggered.connect(self.toggle_pause)
        menu.addAction(self.pause_action)

        restart_action = QAction("Restart", menu)
        restart_action.triggered.connect(self.restart_app)
        menu.addAction(restart_action)

        menu.addSeparator()

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)

        self.is_paused = False

        self.tray.setContextMenu(menu)
        self.tray.show()

        # Setup async task manager
        self.task_manager = AsyncTaskManager()
        self.task_manager.start()

        # Timer to process async events
        self.timer = QTimer()
        self.timer.timeout.connect(self.task_manager.process_events)
        self.timer.start(100)  # Process every 100ms

        # Handle signals for systemd
        signal.signal(signal.SIGTERM, self.handle_signal)
        signal.signal(signal.SIGINT, self.handle_signal)

    def create_colored_theme_icon(self, color):
        """Create keyboard icon with a colored status indicator."""
        base_icon = QIcon.fromTheme("input-keyboard")

        # Get the pixmap from the theme icon
        pixmap = base_icon.pixmap(64, 64).copy()

        # Draw a colored circle indicator in the corner
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw a white background circle for better visibility
        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(36, 36, 28, 28)

        # Draw the colored status indicator
        painter.setBrush(color)
        painter.drawEllipse(38, 38, 24, 24)
        painter.end()

        return QIcon(pixmap)

    def handle_signal(self, signum, frame):
        print(f"\nReceived signal {signum}, shutting down...")
        self.quit_app()

    def toggle_pause(self):
        if self.is_paused:
            # Resume
            self.task_manager.resume()
            self.pause_action.setText("Pause HID")
            self.status_action.setText("Running")
            self.tray.setToolTip("Lily58 HID Manager - Running")
            self.tray.setIcon(self.icon_green)  # Green icon
            print("HID resumed")
        else:
            # Pause
            self.task_manager.pause()
            self.pause_action.setText("Resume HID")
            self.status_action.setText("Paused")
            self.tray.setToolTip("Lily58 HID Manager - Paused")
            self.tray.setIcon(self.icon_red)  # Red icon
            print("HID paused")
        self.is_paused = not self.is_paused

    def restart_app(self):
        """Restart the Python process completely."""
        print("Restarting application...")
        self.timer.stop()
        self.task_manager.stop()
        self.tray.hide()

        # Get the Python executable and script path
        python = sys.executable
        script = os.path.abspath(sys.argv[0])

        # Start a new process with the same arguments
        os.execv(python, [python] + sys.argv)

    def quit_app(self):
        print("Stopping tasks...")
        self.timer.stop()
        self.task_manager.stop()
        self.tray.hide()
        QApplication.quit()

    def run(self):
        return self.app.exec()

# ---------- Main ----------
def main():
    app = TrayApp()
    sys.exit(app.run())

if __name__ == '__main__':
    main()