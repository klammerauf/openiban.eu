# OpenIBAN.eu – next milestones

Established scope: personal non-commercial project, GitHub `klammerauf/openiban.eu`,
Germany at launch, domain `openiban.eu`, website planned at lima-city.

## Initial implementation

- [x] Independent Python/FastAPI application and German IBAN validation.
- [x] Import and version the public Bundesbank TXT file.
- [x] Activate reviewed data and roll back.
- [x] Return bank data with source and validity.
- [x] Local instructions and automated tests.

## Next steps

- [x] Publish source code on GitHub and adopt the MIT License.
- [x] Deploy the API on Ubuntu and import a real Bundesbank dataset.
- [x] Hosting: API at Hetzner, website at lima-city.
- [ ] Complete import diff view and detection of unusual dataset changes.
- [x] Automatically detect new source files, approve them and activate on schedule.
- [ ] Website for visitors with an IBAN form and API explanation.
- [ ] Protected maintainer area with roles, login and approval workflow.
- [ ] Contribution system with source evidence; clarify changes to official data.
- [ ] Database migrations and PostgreSQL integration tests before PostgreSQL operation.
- [ ] Test hosting, TLS, abuse protection, monitoring and recovery.
- [ ] Public pilot operation, followed by release 1.0.

Adapting a company FastAPI application as an API client is a later, separate
integration task. It is neither a prerequisite nor part of this personal
repository. Additional country adapters are available for the next implementation;
see [Source review and outstanding approvals](european-directories.md).
Verification of the original Greek file and usage questions for PL/LV/GR remain open.

Implemented: HTTPS, proxy rate limits, local daily backups and SMTP warnings.
Outstanding: external outage monitoring, external backups and a recovery test.
