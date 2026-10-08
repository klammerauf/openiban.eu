# Europäische Bankverzeichnisse

Stand der Quellenprüfung: 8. Oktober 2026. Dieser Entwicklungsstand wurde nicht
auf den öffentlichen Dienst ausgerollt. Deutschland behält seinen bisherigen
Importer und automatischen Updater. Acht zusätzliche Adapter sind enthalten;
Griechenland ist **vorläufig**, weil der Originaldownload in der Entwicklungsumgebung
HTTP 403 liefert. Sein XLSX-Header und eine vollständige reale Datei müssen vor
Freigabe noch geprüft werden. Synthetische Tests ersetzen diese Prüfung nicht.

## Quellen, Formate und Kennungen

Die Positionen sind einsbasiert und beziehen sich auf die normalisierte IBAN.

| Land | Offizielle Quelle | Importformat | IBAN-Kennung | Aktualisierung / Ergebnis Originalprüfung |
|---|---|---|---|---|
| CH | [SIX Swiss Bank Master v3](https://www.six-group.com/de/products-services/banking-services/interbank-clearing/online-services/download-bank-master.html) | UTF-8 CSV, Semikolon | 5–9, fünfstellige IID/QR-IID | täglich; 1.164 Datensätze am 08.10.2026, davon 26 verkettete IIDs |
| PL | [NBP EWIB 2.0](https://ewib.nbp.pl/faces/pages/faq.xhtml) | JSON, `listaWlascicieli` | 5–12, achtstellige Clearingkennung | bei Änderungen; vollständige API-Antwort mit 3.141 Clearingkennungen geprüft |
| LT | [Bank of Lithuania](https://www.lb.lt/en/iban-and-financial-institution-codes) | englischer CSV-Export, Windows-1257, Semikolon | 5–9, fünfstelliger National ID | bei Änderungen; Export vom 05.05.2026 mit 229 Datensätzen geprüft |
| BE | [National Bank of Belgium](https://www.nbb.be/en/payments-and-securities/bank-identification-codes) | vollständige XLSX-Liste | 5–7, dreistellige Kennung | bei Änderungen; Version 01.09.2026, 782 zugeordnete Kennungen, 218 freie/nicht verfügbare ausgeschlossen |
| CZ | [Czech National Bank](https://www.cnb.cz/cs/platebni-styk/ucty-kody-bank/) | UTF-8 CSV mit BOM, Semikolon | 5–8, vierstelliger Zahlungssystemcode | bei Änderungen; Liste gültig ab 01.10.2026, 47 Datensätze geprüft |
| LV | [Latvijas Banka](https://www.bank.lv/en/operational-areas/payment-systems/identification-of-bic-by-iban) | verlinkte englische XLS-Datei | 5–8, vier Buchstaben | bei Änderungen; 20 Datensätze geprüft |
| SI | [Banka Slovenije](https://www.bsi.si/sl/placilni-sistemi/placilni-in-transakcijski-racun) | UTF-8 HTML-Tabelle | 5–9 exakt, sonst 5–6 als Bankpräfix | bei Änderungen; 18 Kennungen geprüft, einschließlich `rowspan` und fehlendem BIC |
| GR | [Bank of Greece SEPA](https://www.bankofgreece.gr/en/main-tasks/payment-systems-and-settlements/sepa) | verlinkte XLSX-Datei | 5–7, dreistelliger Bank Identifier | **Originaldatei nicht geprüft**, Download HTTP 403; vorläufiger Headeradapter |

IBAN-Längen und BBAN-Formate folgen dem
[SWIFT IBAN Registry](https://www.swift.com/swift-resource/9606/download?language=en).
Die Prüfung umfasst Format und MOD-97, keine nationalen Kontoprüfziffern.
Die griechische Kontokomponente darf alphanumerisch sein, ebenso die schweizerische
und lettische. Liechtenstein wird durch den CH-Adapter nicht automatisch unterstützt.

### Verarbeitung der Quellen

- **CH:** Die CSV enthält 21 Datenfelder und einen zusätzlichen Zeitstempel im Header.
  IIDs werden auf fünf Stellen mit führenden Nullen dargestellt. Typ 4 ist eine
  QR-IID im Bereich 30000–31999; deren eigene Zuordnung bleibt erhalten. Verkettete
  Kennungen (`Concatenation=Y`) sind gelöscht und behalten die Nachfolgekennung als
  Hinweis. IBANs werden nie auf eine Nachfolgekennung umgeschrieben. Der `Valid on`-Tag
  muss für alle Zeilen übereinstimmen und darf nicht nach dem Importbeginn liegen.
- **PL:** Vollständiger Download von
  `https://ewib.nbp.pl/api/v1/zapytanie1/?format=json`, ohne Konto-/IBAN-Eingaben.
  Hauptsitz und organisatorische Einheiten werden einschließlich ihrer Clearingcodes
  verarbeitet. Der allgemeine `BIC` wird verwendet; `BIC SEPA`, TARGET- und SORBNET-BICs
  werden nicht als Ersatz erfunden. Fehlende BICs bleiben `null`.
- **LT:** Der englische Export enthält Bank- und Filialkennungen. Bankname, BIC,
  Ort und Postleitzahl werden übernommen. Eine abschließende vollständig leere
  gepolsterte Zeile ist erlaubt; interne Lücken oder unbekannte Spalten scheitern.
- **BE:** Führende Nullen bleiben erhalten; getrennte BIC-Komponenten werden
  zusammengefügt. `VRIJ` und `Onbeschikbaar` sind keine Banken. Die beobachteten
  BIC-Platzhalter `N/A`, `NAV`, `nav`, `NYA` und `-` bedeuten fehlender BIC. Der
  englische Name wird bevorzugt, sonst Niederländisch, Französisch, Deutsch.
- **LV:** Die XLS-Datei liefert vollständige BICs. Die HTML-Seite teilt BICs über
  Zellen auf und wird bewusst nicht als Datenformat verwendet. `X` im achten
  BIC-Zeichen und `XXX` als Filialcode sind gültige Bestandteile, keine Platzhalter.
- **SI:** Zwei- und fünfstellige Kennungen bleiben unterschiedlich. Lookup verwendet
  zuerst die exakte fünfstellige Kennung, dann das zweistellige Bankpräfix. Damit
  werden Zahlungsinstitute mit eigener fünfstelliger Kennung korrekt getrennt.
  Zusammengefasste Namens-/Adresszellen werden über `rowspan` aufgelöst.
- **GR:** Vorläufige XLSX-Erkennung über eindeutige Spalten `Bank`/`Bank Name`/`Name`/`PSP`,
  `BIC`/`BIC Code` und `Bank Identifier`/`Bank Identifiers`. Ein unbekannter Header
  scheitert statt Daten zu raten. Mit einer realen Originaldatei prüfen und ggf.
  den Adapter samt Regressionstest anpassen, bevor er freigegeben wird.

## Nutzungsbedingungen und Freigabestatus

Der MIT-lizenzierte Programmcode verleiht keine Rechte an den Quelldaten. Es
werden keine Originalverzeichnisse ins Repository kopiert oder neu lizenziert.
Die Tests enthalten synthetische Namen/Kennungen, einschließlich einer synthetischen
XLS-Datei. Bankdaten werden lokal abgefragt; keine eingegebene IBAN wird an eine
Datenquelle übertragen. Jede API-Antwort mit Bestand nennt Publisher und Quellen-URL.

| Land | Geprüfte Grundlage | Konsequenz / offener Punkt |
|---|---|---|
| CH | [Spezifische Swiss Bank Master v3 Dateibeschreibung, S. 1](https://www.six-group.com/dam/download/banking-services/interbank-clearing/bc-bank-master/bankmaster-v3.0-record-description-en.pdf) erlaubt freie Verwendung der Informationen; BIC-Eigentum SWIFT und Haftungsausschluss werden genannt. [Allgemeine SIX-Websitebedingungen](https://www.six-group.com/en/services/legal/terms-and-conditions/terms-of-use.html) sind enger. | Die spezifische Downloadregel bildet die Arbeitsgrundlage; Quelle nennen, keine zusätzlichen Rechte behaupten. |
| PL | [EWIB FAQ](https://ewib.nbp.pl/faces/pages/faq.xhtml) dokumentiert öffentliche API ohne Authentifizierung und vollständige Listenabfragen. | Das bestätigt technischen Zugang, keine ausdrückliche Weiterverbreitungslizenz. Anwendbare Nutzungsrechte vor öffentlicher Aktivierung gesondert klären und dokumentieren. |
| LT | [Terms of use](https://www.lb.lt/en/terms-of-use) verlangt Quellenangabe und ggf. Autorennennung. | Bank of Lithuania als Quelle; keine eigenständige Open-Data-Lizenz behaupten. |
| BE | [Copyright and use of information](https://www.nbb.be/en/disclaimer-and-legal-information/copyright-and-use-information) erlaubt Verwendung, Verteilung und Reproduktion bei Integrität, Genauigkeit und Quellenangabe. | Bei kostenpflichtiger Weitergabe Hinweis auf kostenlose Verfügbarkeit bei NBB; Sonderbedingungen einzelner Inhalte beachten. |
| CZ | [CNB Websitebedingungen](https://www.cnb.cz/en/privacy-statement-and-disclaimer/disclaimer-copyright/) erlaubt Speicherung, Verbreitung und Reproduktion eigener Informationen mit Quellenangabe; Inhalt nicht verfälschen. | Technische Normalisierung, unveränderter Informationsgehalt; keine redaktionellen Korrekturen. |
| LV | [Use of data](https://www.bank.lv/en/statistics/information-for-data-users/use-of-data) erlaubt statistische Wiederverwendung mit Quellenangabe und unveränderten Daten, ggf. Kostenlosigkeitshinweis. | Diese Regel betrifft Statistik. Ihre Geltung für das Zahlungsverkehrsverzeichnis ist nicht bestätigt; vor öffentlicher Aktivierung klären. |
| SI | [Pogoji uporabe](https://www.bsi.si/sl/pogoji-uporabe) erlaubt Speicherung, Reproduktion und Verteilung mit Quellenangabe und unveränderten Daten; besondere Vorgaben für Werbung und kostenpflichtige Inhalte. | Nichtkommerzieller Dienst mit Quellenangabe; kommerzielle/werbliche Nutzung erfordert gesonderte Prüfung. |
| GR | [Terms of use](https://www.bankofgreece.gr/en/useful-links/terms-of-use) war hier nicht abrufbar. | Nutzung und Originalschema noch nicht abschließend geprüft. Eine CC-BY-Regel des separaten Open-Data-Portals wird nicht auf diese Datei übertragen. |

Dies ist eine dokumentierte technische Quellenprüfung, keine Rechtsfreigabe.
`activate-directory` verlangt eine protokollierte Prüfanmerkung. Für PL, LV und
GR muss diese insbesondere die bislang offenen Nutzungsfragen abdecken. Für GR
muss zusätzlich eine erfolgreiche Prüfung mit einem Originalverzeichnis vorliegen.
Ein erfolgreicher Parserlauf oder eine beliebige Prüfanmerkung beweist keine Lizenz.

## Maintainer-Ablauf

Vor dem ersten Start dieser Version: Datenbank sichern, danach `openiban init-db`
ausführen. Die neuen Tabellen `directory_versions`, `directory_banks`,
`directory_active` und `directory_activations` werden zusätzlich angelegt.
Bestehende deutsche Tabellen/Zeiger bleiben erhalten. Dies ist kein allgemeines
Migrationssystem; PostgreSQL bleibt ohne Integrationstest nicht freigegeben.

```bash
openiban init-db
openiban fetch-directory CZ data/cz.csv
openiban import-directory CZ data/cz.csv \
  --source-url https://www.cnb.cz/cs/platebni-styk/.galleries/ucty_kody_bank/download/kody_bank_CR.csv \
  --valid-from 2026-10-01 --valid-until 2026-11-01
openiban directory-versions CZ
```

Die Daten im Beispiel sind eine vom Maintainer gewählte Prüfungsspanne, keine vom
Publisher zugesicherte Laufzeit. Vor jedem Import **Quellstand und angemessenes
Frischeende** bestimmen. SIX `Valid on` und NBB `Version` werden zusätzlich mit dem
Beginn abgeglichen; übrige Quellen brauchen Angaben des Maintainers.

LT und LV: `fetch-directory` entdeckt den aktuellen englischen Downloadlink auf
der offiziellen Seite. Mehrdeutige oder fehlende Links werden nicht geraten.
Mit `--source-url` kann ein manuell geprüfter aktueller Link angegeben werden.
Die LT-Downloadseite liefert in dieser Umgebung HTTP 403, während der explizite
aktuelle CSV-Link funktioniert. LV-Linkentdeckung wurde erfolgreich live geprüft.
WAF-/HTTP-Fehler können einen manuellen Download im Browser erfordern. Offlineimporte
benötigen die tatsächliche offizielle `--source-url`; deren Domainprüfung ist kein
Herkunftsnachweis der lokalen Datei. SHA-256 dient zur Wiedererkennung, nicht als Signatur.

Download prüft das native Format und schreibt keine vorhandene Datei über.
Redirects bleiben bei den konfigurierten offiziellen HTTPS-Hosts; Downloads haben
30 Sekunden Socket-Timeout und maximal 20 MiB. XLSX-Dekompression ist auf 100 MiB
begrenzt; XML-Entitäten, Formeln und Fehlerzellen werden nicht akzeptiert.
Bekannte Tabellenstruktur, Kennungsformat, BIC-Syntax und eindeutige Kennungen
werden geprüft. Ein Parsingfehler schreibt keine Version und aktiviert nichts.

Importausgabe (`added`, `removed`, `changed`, `ignored_rows`, `comparison_version`)
mit dem bisherigen und dem offiziellen Gesamtbestand vergleichen. Große Abnahmen,
fehlerhafte Quellstände und unerwartete Änderungen vor Aktivierung untersuchen.
Diese Länder haben **keine automatische Aktivierung und keine neuen systemd-Timer**.

Nach fachlicher Prüfung, Test und Klärung der Nutzungsbedingungen:

```bash
openiban activate-directory CZ HIER-DIE-VERSION-EINSETZEN \
  --review-note 'Originalstand, Datensatzanzahl, Stichproben und CNB-Nutzungsbedingungen geprüft'
```

Aktivierung erfolgt transaktional je Land und wird mit Prüfanmerkung protokolliert.
Rollback verwendet den gleichen Befehl mit einer früheren Version. Abgelaufene
Versionen erfordern `--allow-expired`; Lookup liefert dann `stale` und keine Bankdaten.
Künftige Versionen lassen sich nicht vor ihrem Gültigkeitsbeginn aktivieren.
Identische Dateien sind pro Land idempotent; abweichende Zeiträume/Quellen-URLs
werden abgelehnt. Die deutsche automatische Aktualisierung bleibt unverändert.

## API und Betrieb

`GET /v1/countries` nennt die neun unterstützten IBAN-Formate. Das Feld
`bank_lookup_supported` bedeutet vorhandene Lookup-Implementierung, nicht aktuell
importierte Bankdaten oder endgültige Quellenfreigabe. Ohne aktivierte aktuelle
Landesversion meldet Lookup `unavailable` bzw. `stale`. Deutsche Bereitschaftsprüfung
`/health/ready` bleibt ein DE-Gesundheitsindikator; sie bestätigt nicht alle Länder.
Ein unbekannter Bankcode ist von einer fehlerhaften IBAN-Prüfsumme unabhängig.
`postal_code`/`city` bleiben leer, wenn die Quelle sie nicht als separate Felder liefert.

Tests: `ruff check .`, `ruff format --check .`, `pytest -q` mit dem aktualisierten
`requirements-dev.lock`. Alle regulären Tests laufen offline. Abgedeckt werden
native Formate, führende Nullen, polnische Einheiten, slowenische Kennungen/Rowspans,
fehlende BICs, reservierte Codes, Schweizer Verkettung/QR-IIDs, beschädigte Dateien,
Größenlimits, Provenienz, Schemaerweiterung, Ländertrennung, CLI, Aktivierung,
Rollback, MOD-97 und API-Lookup. GR ist dabei nur synthetisch geprüft.

Die sieben erreichbaren Originalquellen wurden am 08.10.2026 separat heruntergeladen
und durch die Adapter verarbeitet. Die Originaldateien liegen außerhalb des Repos.
Ein Live-Test ist bewusst kein CI-Test: Quellen/WAFs dürfen die Offline-Suite nicht
beeinflussen. Vor Merge/Release bleibt die Originalprüfung von GR offen; vor einer
öffentlichen Aktivierung bleiben zusätzlich die oben genannten Nutzungsfragen offen.
