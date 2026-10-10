# Poland: direct NBP EWIB 2.0 lookup

Verified on 10 October 2026 against the official service, not just a proposed schema.

## Sources and observed response

- [Official EWIB FAQ](https://ewib.nbp.pl/faces/pages/faq.xhtml): unauthenticated
  REST API, eight-digit `nrRozliczeniowy`, JSON selected with `format=json`.
- [Live query checked](https://ewib.nbp.pl/api/v1/zapytanie1/?nrRozliczeniowy=10100000&format=json).
- [Official API specification](https://ewib.nbp.pl/api/swagger.json).

The checked response was an object with `listaWlascicieli` (a list), not a bank
object at the root. Its owner had `nazwa = Narodowy Bank Polski` and a `siedziba`
with `numeryRozliczeniowe`. The entry with `numer = 10100000` had `numeryBic`
containing `{nazwa: BIC, numer: NBPLPLPWXXX}` and
`{nazwa: BIC SEPA, numer: NBPLPLPWXXX}`. The adapter also handles organizational
units in `jednostki`. Tests use synthetic identifiers; source data is not bundled.

A live query for `00000000` returned an HTML NBP error page. Therefore HTML,
HTTP errors (including 404/429/5xx), malformed JSON, unknown schemas, mismatched
codes and conflicting records mean `unavailable`, not `not_found`. Only a valid
empty `listaWlascicieli` maps to `not_found`; that mapping is a defensive contract
covered by synthetic tests, not a claim that NBP always uses it for absent codes.

## API behavior

`POST /v1/validate` accepts Polish IBANs of 28 characters with a numeric BBAN.
Whitespace removal, ASCII uppercasing and canonical MOD-97 validation happen
locally. Only a valid IBAN triggers a request to EWIB. Characters 5–12 are the
full eight-digit clearing code, preserving leading zeros.

Only that clearing code is sent to NBP; the IBAN, check digits and account number
are not transmitted. The request uses a fixed HTTPS host and path, a five-second
socket timeout, a 1 MiB response limit, no redirects and no automatic retries.
This timeout bounds individual socket operations, not a total request deadline.
No response cache or persistence is introduced. Existing service rate limits
should also protect outgoing lookup volume. NBP availability affects bank lookup
only: a valid IBAN remains valid with `bank_lookup_status = unavailable` and
`bank_code_valid = null`.

Responses include `bank.name`, `bank.bic`, and the optional `bank.bic_sepa`.
Missing BICs are null. BIC SEPA and other BIC labels never replace the general
BIC. Postal code/city come from the matching unit. Source attribution is returned
in `lookup_source` and `lookup_source_url`; `data` is null because this is a live
query, not a versioned local dataset with known validity dates.

The German lookup remains local. `/health/ready` continues to check the German
dataset; it does not promise NBP availability and does not contact NBP.
No domestic NRB/account checksum or account existence verification is performed.
An EWIB match identifies an institution and does not prove an account exists.

## Usage rights

Public API access without authentication confirms technical availability. It
does not establish an open-data license, permission for redistribution, or that
NBP data is covered by this repository's software license. No such license is
asserted here. Review applicable NBP terms before public operation or republishing
results; direct access does not by itself resolve usage rights. This change is
an implementation for review and does not deploy the hosted service.
