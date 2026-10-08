# OpenIBAN.eu – nächste Meilensteine

Festgelegt: persönliches nichtkommerzielles Projekt, GitHub `klammerauf/openiban.eu`,
Deutschland zum Start, Domain `openiban.eu`, Website bei lima-city vorgesehen.

## Erster Entwicklungsstand

- [x] Unabhängige Python-/FastAPI-Anwendung und deutsche IBAN-Prüfung.
- [x] Öffentliche Bundesbank-TXT importieren und versionieren.
- [x] Geprüfte Daten aktivieren und zurücksetzen.
- [x] Bankdaten mit Quelle und Gültigkeit ausgeben.
- [x] Lokale Anleitung und automatisierte Tests.

## Danach

- [x] Quellcode auf GitHub veröffentlichen und MIT-Lizenz festlegen.
- [x] API auf Ubuntu bereitstellen und echten Bundesbank-Bestand importieren.
- [x] Hosting: API bei Hetzner, Website bei lima-city.
- [ ] Vollständige Import-Diff-Ansicht und Erkennung auffälliger Bestandsänderungen.
- [x] Automatische Erkennung neuer Quelldateien, Freigabe und termingerechte Aktivierung.
- [ ] Website für Interessenten mit IBAN-Formular und API-Erklärung.
- [ ] Geschützter Maintainer-Bereich mit Rollen, Anmeldung und Freigabeprozess.
- [ ] Beitragssystem mit Quellenbelegen; Umgang mit Änderungen offizieller Daten klären.
- [ ] Datenbankmigrationen und PostgreSQL-Integrationstests vor PostgreSQL-Betrieb.
- [ ] Hosting, TLS, Missbrauchsschutz, Monitoring und Wiederherstellung testen.
- [ ] Öffentlicher Pilotbetrieb, danach Release 1.0.

Die Anpassung einer Firmen-FastAPI als API-Client ist eine spätere separate
Integrationsaufgabe. Sie ist keine Voraussetzung und kein Bestandteil dieses
privaten Repositorys. Weitere Länder bleiben außerhalb der ersten Version.

Umgesetzt: HTTPS, Proxy-Rate-Limit, lokale tägliche Backups und SMTP-Warnungen.
Offen: externe Ausfallüberwachung, externe Backups und Wiederherstellungstest.
