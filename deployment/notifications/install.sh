#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run using sudo bash.'; exit 1; }
base=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ -x /opt/openiban.eu/.venv/bin/openiban ]]
install -d -m 0700 /etc/openiban /var/lib/openiban-notify
install -m 0755 "$base/notify.py" /usr/local/sbin/openiban-notify.py
/usr/bin/python3 /usr/local/sbin/openiban-notify.py setup
/usr/bin/python3 /usr/local/sbin/openiban-notify.py test
install -m 0644 "$base/openiban-notify.service" /etc/systemd/system/
install -m 0644 "$base/openiban-notify.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now openiban-notify.timer
systemctl start openiban-notify.service
journalctl -u openiban-notify.service -n 10 --no-pager
