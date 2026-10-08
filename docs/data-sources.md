# German data source

Review date: 5 October 2026.

The public bank-code file from Deutsche Bundesbank is the sole bank data source
of the initial version. Every API lookup uses the local active dataset; submitted
IBANs are never sent to the Bundesbank.

## Official references

- [Downloads and validity](https://www.bundesbank.de/de/aufgaben/unbarer-zahlungsverkehr/serviceangebot/bankleitzahlen/download-bankleitzahlen-602592)
- [Guidance and record layout](https://www.bundesbank.de/de/startseite/merkblatt-bankleitzahlendatei-602848)
- [Bank codes and BIC mappings](https://www.bundesbank.de/de/aufgaben/unbarer-zahlungsverkehr/serviceangebot/bankleitzahlen)
- [Terms of use, especially section 4.1](https://www.bundesbank.de/de/startseite/benutzerhinweise/nutzungsbedingungen-fuer-den-allgemeinen-gebrauch-der-website-763554)

## Processing

The initial version processes the public TXT file with 168 bytes per row and
Latin-1 encoding. Only records marked 1 are used for bank lookup. Change marker
D means deleted; an announced deletion alone does not deactivate a bank code.
Successor codes are returned only as hints; IBANs are never rewritten automatically.
Postal codes and cities identify banks rather than providing complete postal addresses.

The software stores source information without editorial corrections. Only field
padding, technical types and representations of missing values are adapted for
the API. Import requires validity dates from the maintainer because the TXT
content does not contain them. Activation follows review.

## Terms of use

Section 4.1 generally permits personal and business storage, distribution and
reproduction of Bundesbank-created information with attribution. It prohibits
alteration or distortion. The bank-code page refers to the legal notices; the
guidance describes the purpose for automated payment processing.

Our initial implementation preserves the information and includes
`Source: Deutsche Bundesbank` in every response with dataset metadata. This is
our working basis, not individual legal approval from the Bundesbank for
OpenIBAN.eu. Before introducing editorial community corrections or our own data
downloads, their permissibility and labeling must be assessed separately.
Source files are neither relicensed nor bundled in this repository.

Development used the publicly available file offered on 5 October 2026, valid
from 7 September to 6 December 2026. The parser was checked against this real
file and synthetic error cases. Future imports must not reuse download links
or validity periods without verification. Regular updates are quarterly.
