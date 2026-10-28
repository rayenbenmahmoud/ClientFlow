# Security policy

ClientFlow CRM is a self-initiated portfolio/demonstration project and has not been deployed to production. It comes with no warranty or support commitment (see `LICENSE`).

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's *private vulnerability reporting* ("Security" tab → "Report a vulnerability") on this repository, or contact the maintainer through the e-mail address on their GitHub profile. Include steps to reproduce and the affected version/commit. Reports are handled on a best-effort basis.

## Before using this code for real customer data

- Review the "Security notes" and "Deployment notes" sections of the README (for example, JWTs are stored in `localStorage` in this demo; production systems should use `httpOnly` cookies).
- Change all demo passwords and never run `seed_demo` against a real database.
- Perform your own security review and make sure your use complies with applicable privacy and data-protection law (e.g. GDPR/CCPA) and your own contractual obligations.
