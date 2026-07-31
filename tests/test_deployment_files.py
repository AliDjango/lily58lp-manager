from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]


def test_installer_migrates_the_old_unit_before_starting_the_new_one() -> None:
    installer = (PROJECT_ROOT / "install-service.sh").read_text()

    assert "lily58lp-manager.service" in installer
    assert "disable --now lily58-manager.service" in installer
    assert 'enable --now "$service_name"' in installer


def test_unit_template_runs_the_packaged_entrypoint() -> None:
    unit = (PROJECT_ROOT / "lily58lp-manager.service").read_text()

    assert "WorkingDirectory=@PROJECT_DIR@" in unit
    assert "ExecStart=@VENV_DIR@/bin/lily58lp-manager" in unit
