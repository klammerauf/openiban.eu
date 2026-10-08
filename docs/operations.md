# Betrieb des ersten Entwicklungsstands

## Lokal

API und Import-CLI verwenden dieselbe Datenbankkonfiguration. Schema einmal mit
`openiban init-db` anlegen, danach API starten. `init-db` kann wiederholt werden,
ist aber kein Werkzeug für zukünftige Schema-Migrationen. Imports und
Aktivierungen durch einen lokalen Maintainer ausführen; keine parallele
Initialisierung. Zugang zur Datenbank entspricht administrativem Zugriff.

Die API speichert oder protokolliert keine IBAN-Anfragen. Standard-Access-Logs
des Servers werden im dokumentierten Startbefehl deaktiviert; Fehlerantworten
übernehmen keine Eingaben. Die Antworten tragen `Cache-Control: no-store`.
IBANs gehören ausschließlich in den JSON-Body. Das Zurückweisen von Query-
Parametern verhindert nicht, dass vorgelagerte Systeme URLs bereits protokollieren.

## Datenfreigabe und Wiederherstellung

1. Datei ausschließlich von der offiziellen Bundesbank-Seite herunterladen.
2. Gültigkeit und Importbericht prüfen, auffällige Änderungen untersuchen.
3. Version ausdrücklich aktivieren; zukünftige Daten werden nur mit eingerichteter Automatik zum Gültigkeitstag aktiv.
4. `/health/ready` und eine bekannte Testabfrage prüfen.
5. Bei einem Fehler die vorige Version aktivieren; abgelaufene Daten bleiben als
   abgelaufen erkennbar und werden nicht als gültige Bankzuordnung ausgegeben.

Zum Sichern der SQLite-Datenbank die API und Importprozesse beenden und
`data/openiban.db` kopieren oder das SQLite-Backup-Verfahren verwenden. Einen
Restore in einer separaten Umgebung testen. Für PostgreSQL ein dafür geeignetes
Backup-/Restore-Verfahren einrichten. Quelldateien separat aufbewahren, sofern
eine spätere identische Rekonstruktion benötigt wird.

## Bereitgestellter Betrieb

Stand 8. Oktober 2026: API auf Ubuntu 24.04 bei Hetzner, Python 3.12,
systemd-Dienst `openiban`, SQLite unter `/var/lib/openiban/openiban.db`.
Nginx leitet an `127.0.0.1:8000` weiter, begrenzt Anfragen und terminiert HTTPS.
Zertifikatserneuerung und lokale tägliche SQLite-Backups wurden geprüft.

- [Automatische Datenaktualisierung](../deployment/auto-update/README.md)
- [SMTP-Warnungen](../deployment/notifications/README.md)

Die Installationsskripte setzen die bestehende API und den Backupdienst voraus;
sie sind keine vollständige Neuinstallation eines leeren Servers.
Der Update-Installer erwartet ein Wheel in seinem Unterordner `wheels`. Bei
Installation aus Git dieses vorher erstellen:

```bash
python -m pip wheel --no-deps . -w deployment/auto-update/wheels
```

Offen bleiben externe Backups, ein Wiederherstellungstest und eine externe
Verfügbarkeitsüberwachung. Der lokale Mailmonitor kann keinen vollständigen
Ausfall seines eigenen Servers melden. Der Code steht unter der MIT-Lizenz. Betreiber-/Datenschutztexte
sind noch festzulegen. Die Website ist bei lima-city geplant.
