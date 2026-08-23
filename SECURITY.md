# Security policy

## Reporting

Use GitHub private vulnerability reporting when available. Do not put API keys, private claims, provider responses, or sensitive audit records in a public issue.

## Trust boundaries

- `VERITAS_MODE=demo` must not make retrieval or model-provider network calls.
- `VERITAS_MODE=live` requires `OPENAI_API_KEY` from the deployment secret store. Never commit it.
- Retrieved titles, snippets, URLs, and model output are untrusted data. Do not render them as raw HTML or follow instructions embedded in them.
- Audit files contain fingerprints and identifiers. They are mutable local files, not signatures, an immutable ledger, or proof that a result is correct.
- Put authentication, TLS, request limits, rate limits, retention, and abuse controls at the deployment boundary before accepting untrusted users.

## Intended use

This is an alpha research prototype. Do not use it for medical, legal, journalistic, election, employment, identity, access-control, or other high-impact decisions.
