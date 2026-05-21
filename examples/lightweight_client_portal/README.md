# Lightweight Client Portal

This example shows Journey's core workflow without a database, server, or generated app.

Try:

```bash
journey status examples/lightweight_client_portal
journey validate examples/lightweight_client_portal
journey doctor examples/lightweight_client_portal
journey diff examples/lightweight_client_portal --check
journey agent examples/lightweight_client_portal --no-test -o /tmp/journey-client-portal-handoff
```

The `.journey/` folder maps the repo journey, page journeys, and API journey that coding agents should read before editing the app.
