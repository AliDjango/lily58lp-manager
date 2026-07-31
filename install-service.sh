#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv_dir="$project_dir/.venv"
service_name="lily58lp-manager.service"
unit_dir="$HOME/.config/systemd/user"
config_dir="$HOME/.config/lily58lp-manager"
template="$project_dir/lily58lp-manager.service"
target="$unit_dir/$service_name"

if [[ ! -x "$venv_dir/bin/lily58lp-manager" ]]; then
    echo "Missing $venv_dir/bin/lily58lp-manager. Run 'uv sync' first." >&2
    exit 1
fi

mkdir -p "$unit_dir" "$config_dir"

# Escape the replacement delimiter and ampersand for sed substitutions.
escaped_project_dir="$(printf '%s' "$project_dir" | sed 's/[&|]/\\&/g')"
escaped_venv_dir="$(printf '%s' "$venv_dir" | sed 's/[&|]/\\&/g')"
sed \
    -e "s|@PROJECT_DIR@|$escaped_project_dir|g" \
    -e "s|@VENV_DIR@|$escaped_venv_dir|g" \
    "$template" > "$target"
chmod 644 "$target"

if [[ ! -e "$config_dir/environment" ]]; then
    cp "$project_dir/environment.example" "$config_dir/environment"
    chmod 600 "$config_dir/environment"
fi

systemctl --user daemon-reload
# A previous install used this unit name.  Stop it before enabling the renamed unit
# so two processes cannot compete for the same HID interface.
systemctl --user disable --now lily58-manager.service >/dev/null 2>&1 || true
systemctl --user enable --now "$service_name"

echo "Installed $service_name. Configure optional room sensors in $config_dir/environment."
