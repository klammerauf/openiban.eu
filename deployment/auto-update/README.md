# Automatische Aktualisierung – Version 0.2.0

Für die bestehende Installation unter `/opt/openiban.eu` mit Benutzer `openiban`,
SQLite unter `/var/lib/openiban/openiban.db` und `openiban-backup.service`.

ZIP im Home-Verzeichnis entpacken und ausführen:

```bash
unzip -q ~/OpenIBAN-API-v0.2.0.zip -d ~/openiban-update-v0.2.0
sudo bash ~/openiban-update-v0.2.0/openiban.eu/deployment/auto-update/install.sh
```

Das Skript erstellt eine Datenbanksicherung über den vorhandenen Backupdienst und
sichert die Python-Umgebung unter `/var/backups/openiban-update/<Zeitstempel>/venv`.
Es installiert das enthaltene Wheel ohne neue Abhängigkeiten, startet die API kurz
neu, prüft deren Erreichbarkeit und richtet die Timer ein. Nginx bleibt unverändert.
Der entpackte Ordner enthält den zugehörigen vollständigen Sourcecode. Der installierte
Python-Code liegt im bestehenden venv; die ältere Sourcekopie unter `/opt/openiban.eu/src`
wird nicht überschrieben. Für spätere Entwicklung die neue Sourceversion verwenden.

## Ablauf

- Täglich 04:15 Uhr Europe/Berlin: offizielle Downloadseite lesen, aktuelle und zukünftige
  TXT-Dateien laden, prüfen, versioniert importieren und bereits fällige Daten aktivieren.
- Täglich 00:05 Uhr: vorgemerkte Daten zum Gültigkeitstag aktivieren. Kein API-Neustart nötig.
- Verpasste Timerläufe werden nach Serverstart nachgeholt.
- Download nur über HTTPS von bundesbank.de/www.bundesbank.de, einschließlich Weiterleitungen.
- Datumsangaben werden von der offiziellen Seite gelesen. Unbekannte Quartalszeiträume,
  unklare Links, defekte Dateien und Prüfsummenkonflikte stoppen den Lauf.
- Automatische Freigabe erfordert mindestens 1.000 aktive Banken. Mehr als 10 % neue,
  entfernte oder geänderte Banken, auffälliger BIC-Verlust oder Zeilenzahländerungen
  außerhalb -20/+25 % erfordern eine manuelle Prüfung. Diese Grenzen sind technische
  Schutzregeln, keine Vorgaben der Bundesbank.
- Ein Downloadfehler oder ein letzter erfolgreicher Abruf vor mehr als 48 Stunden sperrt
  die automatische Aktivierung. Der bestehende Bestand bleibt bestehen; die API behandelt
  abgelaufene Daten weiterhin als nicht aktuell.
- Gleicher Zeitraum mit anderer Datei wird nicht automatisch ersetzt. Bereits aktivierte
  Versionen werden nach einem manuellen Rollback nicht erneut automatisch aktiviert.
- Gleiche Dateiprüfsumme mit anderem Zeitraum benötigt wegen des bestehenden eindeutigen
  Hash-Datenmodells eine manuelle Klärung; keine automatische Umdatierung.

## Kontrolle

```bash
sudo journalctl -u openiban-update-check.service -u openiban-update-activate.service -n 80 --no-pager
sudo -u openiban env OPENIBAN_DATABASE_URL=sqlite:////var/lib/openiban/openiban.db /opt/openiban.eu/.venv/bin/openiban update-status
systemctl list-timers 'openiban-update-*' --no-pager
```

Exitcodes: 0 erfolgreich, 1 Fehler, 2 Warnung. Warnungen erscheinen im JSON/Journal
und lassen den betreffenden Service als fehlgeschlagen erscheinen. Timer versuchen
es am nächsten Termin erneut. **Es wird keine E-Mail oder Pushnachricht versandt.**
Journal/Status müssen bis zur Einrichtung eines Monitorings regelmäßig geprüft werden.
Bei weniger als 14 Tagen Restgültigkeit ohne freigegebenen Nachfolger wird gewarnt.

Dateien und atomar gespeicherter Status liegen unter `/var/lib/openiban/updates`.
Die vorhandene Datenbanksicherung enthält die importierten Versionen, aber nicht diesen
Status oder die TXT-Kopien. Diese können über einen frischen Abruf neu aufgebaut werden;
eine dabei verlorene manuelle Zurückstellung muss erneut bewertet werden. Für vollständige
Wiederherstellung den Ordner und die Konfiguration in externe Backups aufnehmen.

## Manuelle Prüfung

`update-status` nennt Kandidaten-ID, Änderungszahlen und Gründe. Erst nach fachlicher
Prüfung und ab dem Gültigkeitstag die bestehende CLI verwenden:

```bash
sudo -u openiban env OPENIBAN_DATABASE_URL=sqlite:////var/lib/openiban/openiban.db /opt/openiban.eu/.venv/bin/openiban activate VERSION-ID
sudo systemctl start openiban-update-check.service
```

## Automatik stoppen / Code zurücksetzen

```bash
sudo systemctl disable --now openiban-update-check.timer openiban-update-activate.timer
sudo systemctl stop openiban-update-check.service openiban-update-activate.service
```

Für ein Code-Rollback API stoppen, das aktuelle `/opt/openiban.eu/.venv` zur Seite
verschieben und die vom Installer genannte Sicherung `venv` mit `cp -a` wieder an
**den ursprünglichen Pfad** `/opt/openiban.eu/.venv` kopieren. Danach API starten.
Die Datenbankstruktur wurde nicht geändert. Eine Datenrücksetzung separat mit der
bestehenden `activate`-CLI durchführen; alte Daten werden dadurch nicht wieder aktuell.
