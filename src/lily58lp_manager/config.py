"""Runtime configuration loaded without an additional dotenv dependency."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

USER_CONFIG_PATH = Path("~/.config/lily58lp-manager/environment").expanduser()
ROOT_ENV_FILENAME = ".env"


def read_environment_file(path: Path) -> dict[str, str]:
    """Read simple KEY=VALUE files, ignoring comments and malformed lines."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return {}

    values: dict[str, str] = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _float_value(values: dict[str, str], name: str, default: float, minimum: float) -> float:
    try:
        return max(float(values.get(name, default)), minimum)
    except TypeError, ValueError:
        return default


def _int_value(values: dict[str, str], name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(int(values.get(name, default)), minimum)
    except TypeError, ValueError:
        return default


@dataclass(frozen=True)
class Config:
    """Settings for the manager process.

    Precedence is explicit environment variables, the project-root `.env`, then
    `~/.config/lily58lp-manager/environment`.
    """

    prometheus_url: str | None
    room_temp_1_query: str
    room_temp_2_query: str
    request_timeout_seconds: float
    telemetry_interval_seconds: float
    persian_layout_index: int

    @classmethod
    def load(
        cls,
        project_directory: Path | None = None,
        user_config_path: Path = USER_CONFIG_PATH,
        environment: dict[str, str] | None = None,
    ) -> Config:
        project_directory = project_directory or Path.cwd()
        values = read_environment_file(user_config_path)
        values.update(read_environment_file(project_directory / ROOT_ENV_FILENAME))

        # Explicit environment variables remain useful for temporary overrides.
        runtime_environment = environment if environment is not None else os.environ
        values.update(
            {key: value for key, value in runtime_environment.items() if key.startswith("LILY58_")}
        )

        prometheus_url = values.get("LILY58_PROMETHEUS_URL", "").strip() or None
        return cls(
            prometheus_url=prometheus_url,
            room_temp_1_query=values.get("LILY58_ROOM_TEMP_1_QUERY", "temperature"),
            room_temp_2_query=values.get(
                "LILY58_ROOM_TEMP_2_QUERY", "thermometer_temperature_celsius"
            ),
            request_timeout_seconds=_float_value(
                values, "LILY58_REQUEST_TIMEOUT_SECONDS", 2.0, 0.1
            ),
            telemetry_interval_seconds=_float_value(
                values, "LILY58_TELEMETRY_INTERVAL_SECONDS", 1.0, 0.1
            ),
            persian_layout_index=_int_value(values, "LILY58_PERSIAN_LAYOUT_INDEX", 1),
        )
