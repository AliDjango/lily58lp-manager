"""KDE keyboard-layout monitor with reconnect behaviour."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from dbus_next import BusType
from dbus_next.aio import MessageBus

LOGGER = logging.getLogger(__name__)


def layer_for_layout(index: int, persian_layout_index: int) -> str:
    return "QWERTY" if index == persian_layout_index else "DVORAK"


class LayoutMonitor:
    def __init__(
        self,
        persian_layout_index: int,
        send_layer: Callable[[str], Awaitable[None]],
        paused: Callable[[], bool],
    ) -> None:
        self._persian_layout_index = persian_layout_index
        self._send_layer = send_layer
        self._paused = paused

    async def _emit_layer(self, index: int) -> None:
        if not self._paused():
            await self._send_layer(layer_for_layout(index, self._persian_layout_index))

    async def run(self, stop_event: asyncio.Event) -> None:
        retry_delay = 1.0
        while not stop_event.is_set():
            try:
                bus = await MessageBus(bus_type=BusType.SESSION).connect()
                introspection = await bus.introspect("org.kde.keyboard", "/Layouts")
                obj = bus.get_proxy_object("org.kde.keyboard", "/Layouts", introspection)
                interface = obj.get_interface("org.kde.KeyboardLayouts")

                await self._emit_layer(await interface.call_get_layout())

                def layout_changed(index: int) -> None:
                    asyncio.create_task(self._emit_layer(index))

                interface.on_layout_changed(layout_changed)
                LOGGER.info("Listening for KDE keyboard layout changes")
                retry_delay = 1.0
                await stop_event.wait()
                bus.disconnect()
            except asyncio.CancelledError:
                raise
            except Exception as error:  # D-Bus availability varies across sessions
                LOGGER.warning(
                    "KDE layout monitor disconnected: %s; retrying in %.0fs",
                    error,
                    retry_delay,
                )
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=retry_delay)
                except TimeoutError:
                    retry_delay = min(retry_delay * 2, 30.0)
