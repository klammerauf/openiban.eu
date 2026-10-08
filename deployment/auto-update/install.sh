#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run using sudo bash.' >&2; exit 1; }
package_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
app=/opt/openiban.eu
[[ -x "$app/.venv/bin/python" && -f /var/lib/openiban/openiban.db ]]
wheel="$package_dir/wheels/openiban_eu-0.2.0-py3-none-any.whl"
[[ -f "$wheel" ]]
getent passwd openiban >/dev/null
systemctl is-active --quiet openiban
systemctl start openiban-backup.service
backup_dir="/var/backups/openiban-update/$(date -u +%Y%m%dT%H%M%S%NZ)"
install -d -m 0700 "$backup_dir"
cp -a "$app/.venv" "$backup_dir/venv"
for unit in openiban-update-check openiban-update-activate; do
    for suffix in service timer; do
        if [[ -f "/etc/systemd/system/$unit.$suffix" ]]; then
            cp -a "/etc/systemd/system/$unit.$suffix" "$backup_dir/"
        fi
    done
    systemctl stop "$unit.timer" "$unit.service" 2>/dev/null || true
done
echo "Backup of the previous Python environment: $backup_dir/venv"
"$app/.venv/bin/python" -m pip install --no-deps --no-index "$wheel"
"$app/.venv/bin/python" -c 'from openiban.updater import auto_check; from openiban import __version__; assert __version__ == "0.2.0"'
install -d -o openiban -g openiban -m 0750 /var/lib/openiban/updates
systemctl restart openiban
if ! "$app/.venv/bin/python" - <<'PY'
import json
import time
from urllib.request import urlopen
for attempt in range(15):
    try:
        with urlopen('http://127.0.0.1:8000/health/live', timeout=2) as response:
            assert json.load(response)['status'] == 'ok'
        break
    except Exception:
        if attempt == 14:
            raise
        time.sleep(1)
PY
then
    echo "API startup failed. Timers remain disabled. Backup: $backup_dir/venv" >&2
    exit 1
fi
for unit in openiban-update-check openiban-update-activate; do
    install -m 0644 "$package_dir/$unit.service" /etc/systemd/system/
    install -m 0644 "$package_dir/$unit.timer" /etc/systemd/system/
done
systemctl daemon-reload
if ! systemctl start openiban-update-check.service; then
    echo 'The initial download reported an error or warning. Check the journal.' >&2
    journalctl -u openiban-update-check.service -n 40 --no-pager
fi
systemctl enable --now openiban-update-check.timer openiban-update-activate.timer
systemctl list-timers 'openiban-update-*' --no-pager
echo 'Installation complete. Details: deployment/auto-update/README.md'
