#!/usr/bin/env python3
import sys
import asyncio
import psutil
import struct
import threading
import signal
import hid

# DBus imports
from dbus_next.aio import MessageBus
from dbus_next import BusType

# Qt Imports (PyQt6 is standard for KDE environment)
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QAction, QIcon, QPixmap, QColor, QPainter
from PyQt6.QtCore import QObject, pyqtSignal

# ---------- Configuration ----------
VENDOR_ID     = 0x1209
PRODUCT_ID    = 0x5800
USAGE_PAGE    = 0xFF60
USAGE         = 0x61
REPORT_LENGTH = 32

PERSIAN_INDEX = 1  # KDE layout index for Persian

# ---------- Global Control State ----------
class StateController:
    def __init__(self):
        self.paused = False
        self.running = True

state = StateController()

# ---------- HID Functions ----------
def get_raw_hid_interface():
    # If paused, explicitly return None so we don't touch the device
    if state.paused:
        return None

    devices = hid.enumerate(VENDOR_ID, PRODUCT_ID)
    raw_hid_interfaces = [d for d in devices if d['usage_page'] == USAGE_PAGE and d['usage'] == USAGE]

    if not raw_hid_interfaces:
        return None

    try:
        interface = hid.Device(path=raw_hid_interfaces[0]['path'])
        return interface
    except Exception:
        return None

def send_raw_report(data_bytes):
    if state.paused:
        return

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
        # Closing is crucial here to free the device for other apps
        interface.close()

def send_layer_command(layer_name: str):
    if state.paused:
        return
    print(f"Switching to {layer_name}")
    data = [ord(c) for c in layer_name]
    send_raw_report(data)

# ---------- System Info ----------
def get_cpu_temp():
    temps = psutil.sensors_temperatures()
    if "coretemp" in temps:
        return int(sum(t.current for t in temps["coretemp"]) / len(temps["coretemp"]))
    elif "cpu_thermal" in temps:
        return int(temps["cpu_thermal"][0].current)
    return 0

def get_system_status():
    cpu_temp = get_cpu_temp()
    cpu_percent = int(psutil.cpu_percent(interval=None)) # Interval None is non-blocking
    gpu_temp = 0
    gpu_percent = 0
    ram_usage = int(round((psutil.virtual_memory().total - psutil.virtual_memory().available) / 1024 / 1024 / 1024,0))
    ram_percent = int(psutil.virtual_memory().percent * 10)
    vram_usage = 0
    vram_percent = 0
    room_temp_1 = 252
    room_temp_2 = 252

    packed = struct.pack("<BBBBHHHHHH",
                         cpu_temp, cpu_percent, gpu_temp, gpu_percent,
                         ram_usage, ram_percent, vram_usage, vram_percent,
                         room_temp_1, room_temp_2)
    return packed

# ---------- Async Tasks ----------
async def monitor_kde_layout():
    try:
        bus = await MessageBus(bus_type=BusType.SESSION).connect()
        introspection = await bus.introspect('org.kde.keyboard', '/Layouts')
        obj = bus.get_proxy_object('org.kde.keyboard', '/Layouts', introspection)
        iface = obj.get_interface('org.kde.KeyboardLayouts')

        # Initial check
        try:
            current_index = await iface.call_get_layout()
            if current_index == PERSIAN_INDEX:
                send_layer_command("QWERTY")
            else:
                send_layer_command("DVORAK")
        except Exception as e:
            print(f"Initial layout check failed: {e}")

        def layout_changed_handler(index):
            if state.paused:
                return
            if index == PERSIAN_INDEX:
                send_layer_command("QWERTY")
            else:
                send_layer_command("DVORAK")

        iface.on_layout_changed(layout_changed_handler)
        print("Listening for layout changes...")

        # Keep this task alive
        while state.running:
            await asyncio.sleep(1)

    except Exception as e:
        print(f"DBus Error: {e}")

async def system_telemetry_task():
    print("Sending system telemetry...")
    while state.running:
        if not state.paused:
            # Re-init cpu_percent with interval on first run if needed,
            # but usually calling it with 0.2 previously sets the baseline
            psutil.cpu_percent(interval=None)
            status = get_system_status()
            send_raw_report(status)
        await asyncio.sleep(1)

async def async_main_loop():
    await asyncio.gather(
        monitor_kde_layout(),
        system_telemetry_task()
    )

def start_async_thread(loop):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(async_main_loop())

# ---------- GUI / Tray ----------
def create_placeholder_icon(color):
    # Create a 64x64 icon programmatically
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor("transparent"))
    painter = QPainter(pixmap)
    painter.setBrush(QColor(color))
    painter.drawEllipse(4, 4, 56, 56)
    painter.end()
    return QIcon(pixmap)

class KeyboardTrayApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # Setup Tray
        self.tray_icon = QSystemTrayIcon()
        self.icon_active = create_placeholder_icon("#00FF00") # Green
        self.icon_paused = create_placeholder_icon("#FFA500") # Orange

        self.tray_icon.setIcon(self.icon_active)
        self.tray_icon.setToolTip("Lily58 Bridge (Active)")

        # Menu
        self.menu = QMenu()

        # Actions
        self.toggle_action = QAction("Pause HID (Free Device)", self.menu)
        self.toggle_action.setCheckable(True)
        self.toggle_action.triggered.connect(self.toggle_hid)
        self.menu.addAction(self.toggle_action)

        quit_action = QAction("Quit", self.menu)
        quit_action.triggered.connect(self.quit_app)
        self.menu.addAction(quit_action)

        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()

        # Start Async Thread
        self.new_loop = asyncio.new_event_loop()
        self.t = threading.Thread(target=start_async_thread, args=(self.new_loop,), daemon=True)
        self.t.start()

    def toggle_hid(self):
        if self.toggle_action.isChecked():
            state.paused = True
            self.tray_icon.setIcon(self.icon_paused)
            self.tray_icon.setToolTip("Lily58 Bridge (Paused)")
            print("HID Paused - Device freed")
        else:
            state.paused = False
            self.tray_icon.setIcon(self.icon_active)
            self.tray_icon.setToolTip("Lily58 Bridge (Active)")
            print("HID Resumed")

    def quit_app(self):
        state.running = False
        self.tray_icon.hide()
        self.app.quit()
        # The daemon thread will be killed automatically,
        # or we can stop the loop nicely if needed.
        sys.exit(0)

    def run(self):
        sys.exit(self.app.exec())

if __name__ == '__main__':
    # Handle Ctrl+C in terminal gracefully
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    try:
        tray_app = KeyboardTrayApp()
        tray_app.run()
    except KeyboardInterrupt:
        print("\nExiting...")