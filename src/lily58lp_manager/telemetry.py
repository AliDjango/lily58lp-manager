"""Collect and encode the telemetry report consumed by the keyboard firmware."""

from __future__ import annotations

import asyncio
import logging
import struct

import psutil
import requests

from .config import Config
from .logging_utils import RateLimitedWarnings

LOGGER = logging.getLogger(__name__)
WARNINGS = RateLimitedWarnings(LOGGER)
REPORT_FORMAT = "<BBBBHHHHHH"
TELEMETRY_PAYLOAD_LENGTH = struct.calcsize(REPORT_FORMAT)


def clamp(value: int | float, maximum: int) -> int:
    return max(0, min(int(value), maximum))


def cpu_temperature() -> int:
    temperatures = psutil.sensors_temperatures()
    for sensor_name in ("coretemp", "cpu_thermal"):
        readings = temperatures.get(sensor_name, [])
        if readings:
            return clamp(sum(reading.current for reading in readings) / len(readings), 0xFF)
    return 0


def local_metrics() -> tuple[int, int, int, int]:
    memory = psutil.virtual_memory()
    used_gib = (memory.total - memory.available) / 1024**3
    return (
        cpu_temperature(),
        clamp(psutil.cpu_percent(interval=None), 0xFF),
        clamp(round(used_gib), 0xFFFF),
        clamp(memory.percent * 10, 0xFFFF),
    )


def room_temperature(url: str | None, query: str, timeout: float) -> int:
    if not url or not query:
        return 0
    try:
        response = requests.get(url, params={"query": query}, timeout=timeout)
        response.raise_for_status()
        value = response.json()["data"]["result"][0]["value"][1]
        return clamp(float(value) * 10, 0xFFFF)
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as error:
        WARNINGS.warning(
            f"room-temperature:{query}", "Room-temperature query %r failed: %s", query, error
        )
        return 0


def pack_metrics(
    cpu_temp: int,
    cpu_percent: int,
    ram_usage: int,
    ram_percent: int,
    room_temp_1: int,
    room_temp_2: int,
) -> bytes:
    return struct.pack(
        REPORT_FORMAT,
        clamp(cpu_temp, 0xFF),
        clamp(cpu_percent, 0xFF),
        0,  # GPU temperature is not yet collected.
        0,  # GPU utilization is not yet collected.
        clamp(ram_usage, 0xFFFF),
        clamp(ram_percent, 0xFFFF),
        0,  # VRAM usage is not yet collected.
        0,  # VRAM utilization is not yet collected.
        clamp(room_temp_1, 0xFFFF),
        clamp(room_temp_2, 0xFFFF),
    )


async def collect_report(config: Config) -> bytes:
    """Collect a telemetry payload without blocking the Qt/asyncio event loop."""
    local_task = asyncio.to_thread(local_metrics)
    room_1_task = asyncio.to_thread(
        room_temperature,
        config.prometheus_url,
        config.room_temp_1_query,
        config.request_timeout_seconds,
    )
    room_2_task = asyncio.to_thread(
        room_temperature,
        config.prometheus_url,
        config.room_temp_2_query,
        config.request_timeout_seconds,
    )
    (cpu_temp, cpu_percent, ram_usage, ram_percent), room_1, room_2 = await asyncio.gather(
        local_task, room_1_task, room_2_task
    )
    return pack_metrics(cpu_temp, cpu_percent, ram_usage, ram_percent, room_1, room_2)
