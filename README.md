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
