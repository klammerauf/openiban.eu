# OpenIBAN SMTP monitoring

Install with `sudo bash install.sh`. Enter the recipient address and SMTP password at the hidden password prompt.
The installer sends a test message to the configured recipient, then enables
checks every 30 minutes. SMTP: mail.lima-city.de:587, required STARTTLS with verified TLS, info@openiban.eu.
No extra Python dependencies. Configuration: /etc/openiban/notifications.json (0600).

Checks updater warnings (including data expiry and download freshness), failed jobs,
running API and timers, and a local backup less than 36 hours old. Changed warnings
are sent immediately at the next check, unchanged warnings at most daily. A recovery
message follows a previously notified problem. No IBAN queries or logs are mailed.
Failed mail delivery does not mark the warning delivered, so the next check retries.

This runs on the same server: a server/network outage or SMTP outage cannot reliably
be notified this way. External uptime monitoring is a separate future step. SMTP
acceptance does not prove inbox delivery; check the test message and spam folder.

Status: `sudo journalctl -u openiban-notify.service -n 30 --no-pager`
Test: `sudo python3 /usr/local/sbin/openiban-notify.py test`
Change password: `sudo python3 /usr/local/sbin/openiban-notify.py setup`
Disable: `sudo systemctl disable --now openiban-notify.timer`
