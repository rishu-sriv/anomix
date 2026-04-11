# /tenants:onboard

Onboard a new tenant to FinPulse.

## Usage

`/new-tenant <tenant_id>`

## What this does

1. Add a new entry to `tenantConfig.yml` under `tenantConfig.<tenant_id>` with all required fields
2. Confirm the tenant DB URL is set and reachable
3. Run `POST /admin/tenants/<tenant_id>/init` to create the tenant database and run all migrations

## Required config fields

```yaml
tenantConfig:
  <tenant_id>:
    tenantName: "Human Readable Name"
    dataModel:
      dbUrl: postgresql://user:pass@host:port/dbname
    market_data_provider: polygon  # or alpaca, yfinance
    llm_config:
      default: gemini
      gemini:
        model: gemini-2.5-pro
        temperature: 0.0
    agents: portfolio_analyst,risk_analyst,market_strategist,trade_advisor
    pulseiq:
      intelligence_layer: true
```

## Notes

- Never commit real DB credentials — use Vault references in production: `vault:secret/path/key`
- After adding to `tenantConfig.yml`, restart the service for the new tenant to be picked up
- Confirm migrations ran successfully by checking `GET /admin/tenants/<tenant_id>/health`
