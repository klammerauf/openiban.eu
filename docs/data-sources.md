# Datenquelle Deutschland

Stand der Prüfung: 5. Oktober 2026.

Die öffentliche Bankleitzahlendatei der Deutschen Bundesbank bildet die einzige
Bankdatenquelle der ersten Version. Bei jeder Abfrage arbeitet die API mit dem
lokalen aktiven Bestand; eingegebene IBANs werden nicht an die Bundesbank gesendet.

## Offizielle Referenzen

- [Download und Gültigkeit](https://www.bundesbank.de/de/aufgaben/unbarer-zahlungsverkehr/serviceangebot/bankleitzahlen/download-bankleitzahlen-602592)
- [Merkblatt und Satzaufbau](https://www.bundesbank.de/de/startseite/merkblatt-bankleitzahlendatei-602848)
- [Bankleitzahlen und BIC-Zuordnung](https://www.bundesbank.de/de/aufgaben/unbarer-zahlungsverkehr/serviceangebot/bankleitzahlen)
- [Nutzungsbedingungen, insbesondere Abschnitt 4.1](https://www.bundesbank.de/de/startseite/benutzerhinweise/nutzungsbedingungen-fuer-den-allgemeinen-gebrauch-der-website-763554)

## Verarbeitung

Die erste Version verarbeitet die öffentliche TXT-Datei mit 168 Byte je Zeile
und Latin-1-Zeichencodierung. Für die Bankzuordnung zählen nur Datensätze mit
Merkmal 1. Änderungskennzeichen D bedeutet gelöscht; eine angekündigte Löschung
allein deaktiviert eine BLZ noch nicht. Nachfolgekennungen werden nur als Hinweis
ausgegeben; IBANs werden nicht automatisch umgeschrieben. Postleitzahl und Ort
dienen der Identifikation, nicht als vollständige Postanschrift.

Die Software speichert Quelldaten ohne redaktionelle Korrekturen. Lediglich
Feldauffüllung, technische Typen und die Darstellung fehlender Angaben werden
für die API umgesetzt. Der Import benötigt Gültigkeitsdaten vom Maintainer,
weil der TXT-Inhalt diese nicht enthält. Er wird erst nach Prüfung aktiviert.

## Nutzungsbedingungen

Abschnitt 4.1 erlaubt grundsätzlich persönliche und geschäftliche Speicherung,
Weitergabe und Vervielfältigung der von der Bundesbank erstellten Informationen
mit Quellenangabe. Er untersagt Änderung oder Verfälschung. Die Bankleitzahlenseite
verweist auf die rechtlichen Hinweise; das Merkblatt beschreibt den Zweck für
automatisierten Zahlungsverkehr.

Unsere erste technische Umsetzung erhält den Informationsgehalt und nennt
`Quelle: Deutsche Bundesbank` in jeder Antwort mit Datenversion. Dies ist die
Arbeitsgrundlage, keine individuelle rechtliche Freigabe der Bundesbank für
OpenIBAN.eu. Vor einer späteren redaktionellen Community-Korrektur oder einem
eigenen Datendownload sind deren Zulässigkeit und Kennzeichnung gesondert zu
klären. Quelldateien werden im Repository nicht neu lizenziert oder mitgeliefert.

Bei der Entwicklung wurde die am 5. Oktober 2026 öffentlich angebotene Datei
mit Gültigkeit 7. September bis 6. Dezember 2026 verwendet. Der Parser wurde
gegen diese echte Datei sowie synthetische Fehlerfälle geprüft. Downloadlinks
und Gültigkeitszeiträume dürfen bei künftigen Imports nicht ungeprüft wiederverwendet
werden. Die regulären Aktualisierungen erfolgen vierteljährlich.

## Zusätzliche europäische Verzeichnisse

Die neuen Adapter, Quellenformate, Nutzungsbedingungen, Prüfstand und manuellen
Freigabeschritte sind in [Europäische Bankverzeichnisse](european-directories.md) dokumentiert.
Die ursprüngliche deutsche Import- und Updatearchitektur bleibt erhalten.
