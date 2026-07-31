#!/usr/bin/env python3
import hid
import asyncio
import psutil
import struct

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
    ram_percent = int(psutil.virtual_memory().percent * 10)     # scale 0-1000
    vram_usage = 0                # scale 0-1000
    vram_percent = 0                # scale 0-1000
    #room_temp_1 = int(float(requests.get("http://192.168.1.200:9090/api/v1/query?query=thermometer_temperature_celsius").json()['data']['result'][0]['value'][1])*10)
    #room_temp_2 = int(float(requests.get("http://192.168.1.200:9090/api/v1/query?query=temperature").json()['data']['result'][0]['value'][1])*10)
    try:
        room_temp_1 = int(float(requests.get("http://192.168.1.200:9090/api/v1/query?query=temperature").json()['data']['result'][0]['value'][1])*10)
    except Exception:
        room_temp_1 = 0
    try:
        room_temp_2 = int(float(requests.get("http://192.168.1.200:9090/api/v1/query?query=thermometer_temperature_celsius").json()['data']['result'][0]['value'][1])*10)
    except Exception:
        room_temp_2 = 0
    # Match the C struct layout: uint8, uint8, uint16, uint16, uint8
    # packed = struct.pack("<BBHHB", cpu_temp, gpu_temp, ram, vram, room_temp)
    packed = struct.pack("<BBBBHHHHHH", cpu_temp,cpu_percent,gpu_temp,gpu_percent,ram_usage,ram_percent,vram_usage,vram_percent,room_temp_1,room_temp_2)
    return packed


def get_cpu_temp():
    temps = psutil.sensors_temperatures()
    if "coretemp" in temps:
        return int(sum(t.current for t in temps["coretemp"]) / len(temps["coretemp"]))
    elif "cpu_thermal" in temps:
        return int(temps["cpu_thermal"][0].current)
    return 0


# ---------- KDE Layout Listener ----------
async def monitor_kde_layout():
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
        if index == PERSIAN_INDEX:
            send_layer_command("QWERTY")
        else:
            send_layer_command("DVORAK")

    iface.on_layout_changed(layout_changed_handler)
    print("Listening for layout changes...")

# ---------- System Telemetry Loop ----------
async def system_telemetry_task():
    print("Sending system telemetry...")
    while True:
        status = get_system_status()
        send_raw_report(status)
        await asyncio.sleep(1)  # send every 5 seconds

# ---------- Main ----------
async def main():
    await asyncio.gather(
        monitor_kde_layout(),
        system_telemetry_task()
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")

"""
parse gpu with nvidia-settings  -q "[thermalsensor:0]/ThermalSensorReading" 
multipage slideshow if hid is connected on slave,else bongo
rotate bongo 90 degrees
cpu - ram - gpu - vram order
{PROMETHEUS_URL}/api/v1/query?query=${encodeURIComponent(query)}
th8.1.200:9090";     // Your Prometheus URL
    'temperature': 'ESP32',
    'thermometer_temperature_celsius': 'Mi Temp',
"""