from pathlib import Path

from lily58lp_manager.config import Config, read_environment_file


def test_environment_file_accepts_export_and_quotes(tmp_path: Path) -> None:
    config_file = tmp_path / "environment"
    config_file.write_text(
        "# comment\nexport LILY58_PROMETHEUS_URL='http://user'\nINVALID\nKEY = value\n"
    )

    assert read_environment_file(config_file) == {
        "LILY58_PROMETHEUS_URL": "http://user",
        "KEY": "value",
    }


def test_config_uses_root_env_before_user_config_and_process_environment(
    tmp_path: Path,
) -> None:
    user_config = tmp_path / "user-environment"
    user_config.write_text(
        "LILY58_PROMETHEUS_URL=http://user\nLILY58_TELEMETRY_INTERVAL_SECONDS=5\n"
    )
    (tmp_path / ".env").write_text(
        "LILY58_PROMETHEUS_URL=http://project\nLILY58_TELEMETRY_INTERVAL_SECONDS=2\n"
    )

    project_config = Config.load(tmp_path, user_config, environment={})
    explicit_config = Config.load(
        tmp_path,
        user_config,
        environment={"LILY58_PROMETHEUS_URL": "http://process"},
    )

    assert project_config.prometheus_url == "http://project"
    assert project_config.telemetry_interval_seconds == 2
    assert explicit_config.prometheus_url == "http://process"


def test_config_falls_back_for_invalid_numeric_values(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "LILY58_REQUEST_TIMEOUT_SECONDS=not-a-number\nLILY58_PERSIAN_LAYOUT_INDEX=-2\n"
    )

    config = Config.load(tmp_path, tmp_path / "missing", environment={})

    assert config.request_timeout_seconds == 2
    assert config.persian_layout_index == 0
