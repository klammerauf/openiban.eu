# OpenIBAN.eu

Eigenständiges, nichtkommerzielles Projekt zur IBAN-Prüfung und Abfrage von
Bankdaten, zunächst für Deutschland. Die API läuft mit FastAPI, versionierten Bundesbank-Daten und automatischer Aktualisierung. Keine ERP-Abhängigkeit.

## Funktionsumfang

- Deutsche IBAN: Leerzeichen entfernen, ASCII-Großschreibung, Format/Länge und MOD-97 prüfen.
- Bankname, BIC, BLZ, Postleitzahl und Ort aus dem aktiven Bundesbank-Datenbestand liefern.
- Unbekannte/gelöschte BLZ, fehlende Daten und abgelaufene Daten unterscheiden.
- Öffentliche Bundesbank-TXT prüfen, versioniert importieren und ausdrücklich aktivieren.
- Frühere Datenversion wieder aktivieren; Aktivierungsverlauf bleibt erhalten.
- OpenAPI-Dokumentation unter `/docs` und automatische Tests in GitHub Actions.

`iban_valid` bedeutet **Format und IBAN-Prüfsumme korrekt**. Es bestätigt weder
Kontoexistenz noch Kontoinhaber, Zahlungsfähigkeit oder nationale
Kontoprüfzifferverfahren. Der BLZ-Status steht separat in `bank_code_valid`.
Andere Länder liefern `reason: unsupported_country` und `iban_valid: null`.

## Lokal starten (Python 3.12)

```bash
git clone https://github.com/klammerauf/openiban.eu.git
cd openiban.eu
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
openiban init-db
uvicorn openiban.api:app --host 127.0.0.1 --port 8000 --no-access-log
```

Windows PowerShell: statt `source` den Befehl `.venv\Scripts\Activate.ps1` verwenden.
Die Datenbank liegt standardmäßig unter `data/openiban.db`, relativ zum
Arbeitsverzeichnis. API und Importbefehle aus demselben Verzeichnis starten.
`OPENIBAN_DATABASE_URL` kann einen anderen Datenbankpfad festlegen; `.env.example`
zeigt das Format. Eine `.env`-Datei wird nicht automatisch geladen.

SQLite ermöglicht den lokalen Einstieg ohne Datenbankserver. SQLAlchemy bereitet
PostgreSQL vor (`pip install -e '.[postgres]'` und eine passende Verbindungs-URL).
Dieser erste Stand wurde mit SQLite getestet; PostgreSQL-Integrationstests und
Schema-Migrationen folgen vor einem entsprechenden Produktivbetrieb.

Ohne Datenimport funktioniert die IBAN-Prüfung bereits. Die Bankauskunft meldet
`unavailable`, `/health/ready` liefert 503. `/health/live` zeigt die Erreichbarkeit.

## Bundesbank-Daten importieren

1. Auf der [offiziellen Downloadseite](https://www.bundesbank.de/de/aufgaben/unbarer-zahlungsverkehr/serviceangebot/bankleitzahlen/download-bankleitzahlen-602592)
   die **ungepackte öffentliche TXT-Datei** herunterladen und unter `data/blz.txt` speichern.
   CSV, XML, ZIP und die erweiterte 174-stellige Datei werden in dieser Version nicht akzeptiert.
2. Gültigkeitsbeginn und -ende auf der Downloadseite ablesen. Die Angaben sind
   nicht in den TXT-Zeilen enthalten und müssen beim Import angegeben werden.
3. Import ausführen. Beispiel für die am 5. Oktober 2026 angebotene Datei:

```bash
openiban import-bundesbank data/blz.txt --valid-from 2026-09-07 --valid-until 2026-12-06
```

Für spätere Downloads **die dazugehörigen Daten einsetzen**. Optional kann
`--source-url` den tatsächlichen HTTPS-Downloadlink der Bundesbank dokumentieren.
Der Import führt keine Netzwerkanfragen aus und prüft nicht die Herkunft der
lokalen Datei. SHA-256 dient der Wiedererkennung, nicht als Signatur.

Die Ausgabe enthält Version, SHA-256, Datensatzanzahl sowie die Zahl hinzugekommener,
entfallener und geänderter aktiver Banken gegenüber der derzeit aktiven Version.
Diese Zusammenfassung und die Herkunft vor der Aktivierung kontrollieren.
Auch eine formal gültige Datei kann unvollständig sein; eine vollständige
fachliche Freigabeoberfläche ist noch nicht enthalten.

```bash
openiban versions
openiban activate HIER-DIE-AUSGEGEBENE-VERSION-EINSETZEN
```

Import und Aktivierung sind getrennt. Identische Dateien werden nicht mehrfach
gespeichert. Fehlerhafte Imports lassen den bisherigen Bestand unverändert.
Eine zukünftige Version kann erst ab ihrem Gültigkeitsbeginn aktiviert werden.
Die Datumsauswertung erfolgt in `Europe/Berlin`.

Für einen Rollback denselben Aktivierungsbefehl mit einer früheren Version nutzen.
Eine abgelaufene Version erfordert zusätzlich `--allow-expired`; die API meldet
danach ausdrücklich `stale` und liefert keine veralteten Bankzuordnungen.
Eine spätere Aktivierung ersetzt niemals Teile eines laufenden Datenbestands,
sondern schaltet den Versionszeiger in einer Transaktion um.

Quelldateien und lokale Datenbanken gehören nicht ins Git-Repository. Sichere sie
bei Bedarf separat. Die Datenbank bewahrt die importierten bankleitzahlführenden
Datensätze sowie Import- und Aktivierungsmetadaten auf; Filialdatensätze werden
geprüft und gezählt, aber nicht gespeichert.

## API ausprobieren

```bash
curl -X POST http://127.0.0.1:8000/v1/validate \
  -H 'Content-Type: application/json' \
  -d '{"iban":"DE58 1234 5678 0123 4567 89"}'
```

Dies ist ein synthetisches Beispiel. Seine Prüfsumme ist korrekt; daraus folgt
keine reale Bank- oder Kontoverbindung. Im offiziellen Bestand kann die Antwort
daher `bank_lookup_status: not_found` enthalten.

| Feld | Bedeutung |
|---|---|
| `normalized_iban` | Normalisierte Eingabe; keine Buchstaben/Punktuation entfernt |
| `country_supported` | Deutschland wird unterstützt |
| `iban_valid` | DE-Format und IBAN-Prüfsumme; bei nicht unterstützten Ländern `null` |
| `checks` | Einzelne Format-/Prüfsummenergebnisse; `null` bedeutet nicht geprüft |
| `reason` | `valid`, `invalid_format`, `invalid_characters`, `invalid_checksum`, `unsupported_country` |
| `bank_lookup_status` | `found`, `not_found`, `deleted`, `not_checked`, `unavailable`, `stale` |
| `bank_code_valid` | BLZ im aktuellen Bestand gültig; `null` bedeutet nicht geprüft/prüfbar |
| `bank` | Bankdaten nur für einen aktiven Treffer; sonst `null` |
| `data` | Datenversion, Hash, Quelle, Importzeit und Gültigkeit; sonst `null` |

Fachliche Prüfergebnisse liefern HTTP 200, auch bei ungültiger IBAN oder fehlenden
Bankdaten. HTTP 422 kennzeichnet ein fehlerhaftes Anfrageformat, 413 einen zu
großen Body, 400 nicht unterstützte Query-Parameter. Clients müssen die
Ergebnisfelder auswerten. `GET /v1/countries` zeigt die unterstützten Länder.

## Tests

```bash
ruff check .
ruff format --check .
pytest -q
```

Die Tests verwenden ausschließlich synthetische Datensätze und benötigen keine
Netzwerkverbindung oder Bundesbank-Downloads. `requirements-dev.lock` fixiert die
Entwicklungsabhängigkeiten. Aktualisieren mit:

```bash
uv pip compile pyproject.toml --extra dev --python-version 3.12 --output-file requirements-dev.lock
```

## Datenquelle, Lizenz und nächste Schritte

**Quelle: Deutsche Bundesbank.** Siehe [Quellen und Nutzungsbedingungen](docs/data-sources.md).
Die Datenbedingungen gelten unabhängig von der noch auszuwählenden Codelizenz.
Das Repository ist öffentlich; eine Open-Source-Lizenz wurde bisher nicht festgelegt.

Die API wird unter https://api.openiban.eu auf einem Ubuntu-Server bei Hetzner
betrieben. Nginx übernimmt HTTPS und Rate-Limits. Die Website bei lima-city und
der geschützte Maintainer-Bereich sind noch geplant.
Details: [Roadmap](docs/roadmap.md) und [Betrieb](docs/operations.md).

E-Mail-Warnungen: [Installation und Betrieb](deployment/notifications/README.md).
SMTP-Zugangsdaten und Empfänger werden ausschließlich auf dem Server eingerichtet.

## Automatische Bundesbank-Aktualisierung (0.2.0)

Täglicher Download, Qualitätsprüfung und Aktivierung ab Gültigkeitstag sind als lokale
Maintainer-CLI und systemd-Timer verfügbar. Installation, Grenzwerte, Überwachung und
Rollback: [deployment/auto-update/README.md](deployment/auto-update/README.md).
