# Polish clearing-code directory

OpenIBAN downloads the official EWIB JSON snapshot and looks up the eight-digit
clearing code locally. It sends no request to NBP during IBAN validation.
The response identifies Narodowy Bank Polski and links to its website.
Regular BICs are used when published. Missing BICs are represented by null.
The dataset does not verify account existence.

NBP Help Desk confirmed on 20 October 2026 that it does not object to using
EWIB data in software and IT services. The data themselves should not be resold.
Reuse requires attribution and a link to [NBP](https://www.nbp.pl/).
Section 5 of the [NBP website terms](https://static.nbp.pl/dokumenty/regulaminy/regulamin_nbppl_en.pdf)
allows temporary blocking for excessive automated load.

The [EWIB API](https://ewib.nbp.pl/faces/pages/faq.xhtml) returned 3,141
clearing codes on 9 November 2026, including 2,984 regular BICs.
The JSON feed does not provide a snapshot publication date. API metadata
reports the last successful check and leaves published_on null.

Run openiban init-db before the first openiban update-pl. Use the same database
URL and service account as the API. Point the packaged service at the installed
release executable and run it once before enabling the timer. The timer
downloads one snapshot daily at 06:20 Europe/Berlin with up to 30 minutes of jitter.
The importer requires 2,000 to 6,000 clearing codes and rejects changes exceeding
10% of the active bank name/BIC mappings. Failures preserve the active version
and its last successful check. The API withholds bank data after more than seven
calendar days without a successful check. Stop the timer before a manual rollback.
