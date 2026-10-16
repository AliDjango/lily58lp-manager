# Lily58LP Manager

Lily58LP Manager is a KDE tray application and user-level systemd service. It
sends host telemetry to the Lily58LP raw HID interface and selects `QWERTY` for
the configured Persian KDE layout and `DVORAK` for all other layouts.

## Requirements

- Linux with a KDE graphical session and its session D-Bus available.
- Python 3.14 and [uv](https://docs.astral.sh/uv/).
- HIDAPI support and permission to open the keyboard's raw HID device (usually
  provided by a local udev rule).

## Setup and service installation

```bash
uv sync
./install-service.sh
```

The installer renders and installs `lily58lp-manager.service`, removes the
previous `lily58-manager.service` if it is enabled, and starts the new unit.
Use `systemctl --user status lily58lp-manager.service` and
`journalctl --user -u lily58lp-manager.service -f` to inspect it.

For development, run `uv run lily58lp-manager` from the project root.

## Configuration

Settings are read in this precedence order: explicit process environment,
`./.env` in the project root, then
`~/.config/lily58lp-manager/environment`. The root `.env` takes precedence over
the user configuration file. Copy `environment.example` to either location.

Room-temperature telemetry is disabled unless `LILY58_PROMETHEUS_URL` is set.
The manager uses a two-second request timeout by default and sends zero for a
failed or unavailable sensor. The remaining variables in `environment.example`
control the Prometheus queries, telemetry interval, Persian layout index, and
log level.

## Development checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Legacy manager prototypes are kept under `archive/`; they are not supported
runtime entrypoints. Font-generation helpers remain available under `tools/`.

## VIA compatibility

Use firmware that supports the one-way telemetry command `0x88` (the updated
`lily58lp:upstream` build). The manager writes a leading zero HID report ID,
then a 32-byte report containing `0x88` and the telemetry or layout payload.
The firmware does not reply to this command, leaving the shared input endpoint
for VIA responses. The manager does not read VIA's responses.

Update firmware on both halves before running this manager version. Older
firmware that only accepts `0x85` will ignore these updates. The firmware keeps
`0x85` with its original echo response for legacy clients, which must be stopped
while using VIA. Sharing the device still depends on the host HID backend;
verify on your target machine.

The tray menu's **Pause HID** / **Resume HID** option remains available.
After updating, restart the manager, unplug/reconnect the keyboard to clear
old responses, and reopen one VIA tab with the local V3 definition loaded.
