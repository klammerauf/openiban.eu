#!/usr/bin/python3
"""Local SMTP monitoring; configuration and state are root-only."""

import argparse
import getpass
import json
import os
import smtplib
import ssl
import subprocess
import tempfile
import time
from email.message import EmailMessage
from pathlib import Path

CONFIG = Path("/etc/openiban/notifications.json")
STATE = Path("/var/lib/openiban-notify/state.json")


def save(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as f:
        json.dump(value, f)
        f.flush()
        os.fsync(f.fileno())
        name = f.name
    os.chmod(name, 0o600)
    os.replace(name, path)


def send(config, subject, body):
    message = EmailMessage()
    message["From"] = config["username"]
    message["To"] = config["recipient"]
    message["Subject"] = "[OpenIBAN] " + subject
    message.set_content(body)
    with smtplib.SMTP("mail.lima-city.de", 587, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(config["username"], config["password"])
        smtp.send_message(message)


def run(args):
    return subprocess.run(args, capture_output=True, text=True, timeout=60)


def problems():
    issues = []
    result = run(
        [
            "/usr/sbin/runuser",
            "-u",
            "openiban",
            "--",
            "/usr/bin/env",
            "OPENIBAN_DATABASE_URL=sqlite:////var/lib/openiban/openiban.db",
            "/opt/openiban.eu/.venv/bin/openiban",
            "update-status",
        ]
    )
    if result.returncode not in (0, 2):
        issues.append("Could not read updater status; check the server journal.")
    else:
        try:
            issues.extend(json.loads(result.stdout)["warnings"])
        except (ValueError, KeyError, TypeError):
            issues.append("Updater returned an invalid status format.")
    for unit in [
        "openiban",
        "openiban-update-check",
        "openiban-update-activate",
        "openiban-backup",
    ]:
        if run(["systemctl", "is-failed", unit + ".service"]).stdout.strip() == "failed":
            issues.append(unit + ".service has failed.")
    if run(["systemctl", "is-active", "openiban.service"]).returncode:
        issues.append("API service is not active.")
    for unit in ["openiban-update-check", "openiban-update-activate", "openiban-backup"]:
        if run(["systemctl", "is-active", unit + ".timer"]).returncode:
            issues.append(unit + ".timer is not active.")
    backups = list(Path("/var/backups/openiban").glob("openiban-*.db"))
    if not backups or time.time() - max(p.stat().st_mtime for p in backups) > 36 * 3600:
        issues.append("No local database backup within the last 36 hours.")
    return sorted(set(issues))


def check(config):
    issues = problems()
    previous = json.loads(STATE.read_text()) if STATE.exists() else {}
    now = time.time()
    if issues:
        if issues != previous.get("issues") or now - previous.get("sent", 0) >= 86400:
            send(
                config,
                "Action required",
                "\n".join("- " + item for item in issues)
                + "\n\nCheck details on the server using journalctl.\n",
            )
            save(STATE, {"issues": issues, "sent": now})
            print("Warning sent.")
        else:
            print("Known warning; next reminder after 24 hours.")
    elif previous.get("issues"):
        send(
            config,
            "Recovery",
            "All states checked by the local monitor are healthy again.",
        )
        save(STATE, {"issues": [], "sent": now})
        print("Recovery notification sent.")
    else:
        print("No warnings.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["setup", "test", "check"])
    args = parser.parse_args()
    if args.command == "setup":
        recipient = input("Recipient address for warnings: ").strip()
        if "@" not in recipient or any(c in recipient for c in "\r\n"):
            raise ValueError("Invalid recipient address.")
        password = getpass.getpass("SMTP password for info@openiban.eu (hidden): ")
        if not password:
            raise ValueError("Empty passwords are not allowed.")
        save(CONFIG, {"username": "info@openiban.eu", "password": password, "recipient": recipient})
        print("SMTP credentials stored securely.")
        return
    config = json.loads(CONFIG.read_text())
    if args.command == "test":
        send(
            config,
            "Test message",
            "SMTP delivery for OpenIBAN.eu is working.\n"
            "Recipient: " + config["recipient"] + "\nAutomatic monitoring checks every 30 minutes.",
        )
        print("Test message accepted by SMTP server; check inbox and spam folder.")
    else:
        check(config)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Never print SMTP responses or configuration: they may contain credentials.
        print(
            "Notification failed ("
            + type(exc).__name__
            + "). Check SMTP credentials, network and local configuration.",
            flush=True,
        )
        raise SystemExit(1) from None
