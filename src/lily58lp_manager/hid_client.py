"""Resilient access to the Lily58 raw HID interface."""

from __future__ import annotations

import logging
from collections.abc import Iterable

import hid

from .logging_utils import RateLimitedWarnings

LOGGER = logging.getLogger(__name__)
WARNINGS = RateLimitedWarnings(LOGGER)
VENDOR_ID = 0x1209
PRODUCT_ID = 0x5800
USAGE_PAGE = 0xFF60
USAGE = 0x61
REPORT_LENGTH = 32
HID_REPORT_ID = 0x00
TELEMETRY_COMMAND = 0x88


class HidClient:
    def _open_interface(self):
        try:
            devices = hid.enumerate(VENDOR_ID, PRODUCT_ID)
            interface = next(
                (
                    device
                    for device in devices
                    if device.get("usage_page") == USAGE_PAGE and device.get("usage") == USAGE
                ),
                None,
            )
            if interface is None:
                return None
            return hid.Device(path=interface["path"])
        except Exception as error:  # hid exposes platform-specific exception types
            WARNINGS.warning("open", "Could not open Lily58 HID interface: %s", error)
            return None

    def send(self, payload: Iterable[int]) -> bool:
        """Send one fixed-size raw report and always release the HID interface."""
        data = bytes(payload)
        if len(data) > REPORT_LENGTH - 1:
            raise ValueError(f"HID payload must be at most {REPORT_LENGTH - 1} bytes")

        interface = self._open_interface()
        if interface is None:
            return False

        # HIDAPI requires a leading report ID even for unnumbered HID reports.
        # 0x88 is the firmware's one-way telemetry command: no reply is queued
        # on the shared input endpoint, so VIA can receive its own responses.
        report = bytes([HID_REPORT_ID, TELEMETRY_COMMAND]) + data.ljust(REPORT_LENGTH - 1, b"\0")
        try:
            written = interface.write(report)
            if written != len(report):
                WARNINGS.warning(
                    "short-write", "Incomplete Lily58 HID write: %s/%s bytes", written, len(report)
                )
                return False
            return True
        except Exception as error:  # hid exposes platform-specific exception types
            WARNINGS.warning("write", "Could not write Lily58 HID report: %s", error)
            return False
        finally:
            try:
                interface.close()
            except Exception:
                LOGGER.debug("Could not close Lily58 HID interface", exc_info=True)

    def send_layer(self, layer_name: str) -> bool:
        return self.send(layer_name.encode("ascii"))
