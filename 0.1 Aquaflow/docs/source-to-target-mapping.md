# Source-to-Target Mapping (STTM)

Legacy on‑prem SQL Server → Databricks Medallion → serving (Power BI, Salesforce).
Synthetic/illustrative; column names mirror the demo factories in
`src/data_generator.py`.

## 1. Customer dimension (`DimCustomer`, SCD2)

| # | Source (legacy) | Target (Silver `DimCustomer`) | Type | Rule / transformation | CDE? |
|---|---|---|---|---|---|
| 1 | `dbo.Account.AcctNo` | `account_id` | STRING | Trim; business key | Key |
| 2 | `dbo.Account.PlanCd` | `plan_type` | STRING | Map code→label (`R`→`RESIDENTIAL`, `C`→`COMMERCIAL`, `X`→`CONCESSION`) | **Yes** |
| 3 | `dbo.Property.PropId` | `property_id` | STRING | FK to `DimProperty` | **Yes** |
| 4 | *(derived)* | `record_hash` | STRING | `sha2(concat_ws('||', CDEs), 256)` | — |
| 5 | *(derived)* | `effective_start` / `effective_end` / `is_current` | TS/TS/BOOL | SCD2 control (see ADR 0002) | — |

## 2. Billing fact (`FactBilling`, Gold)

| # | Source | Target | Type | Rule | CDE? |
|---|---|---|---|---|---|
| 1 | `dbo.Billing.AcctNo` | `account_id` | STRING | FK → `DimCustomer` (current) | Key |
| 2 | `dbo.Billing.BillDt` | `bill_date` | DATE | Cast; grain = account × day | Key |
| 3 | `dbo.Billing.Amt` | `total_billed` | DECIMAL(12,2) | Sum of line items (replaces cursor loop) | **Yes** |
| 4 | *(pipeline)* | `ingestion_ts` | TS | Audit — **excluded** from reconciliation hash | — |

## 3. Salesforce outbound (Gold `Customer360` → Salesforce)

| # | Gold field | Salesforce object.field | Rule / strategy |
|---|---|---|---|
| 1 | `account_id` | `Account.External_Id__c` | Upsert external id (idempotent) |
| 2 | `plan_type` | `Account.Plan_Type__c` | Picklist; current SCD2 version only |
| 3 | `property_id` | `Property__c.External_Id__c` | Related object upsert |
| 4 | `total_billed` (MTD) | `Account.MTD_Billed__c` | Aggregate; refresh cadence per contract |

**Delivery:** ADF Salesforce sink / Bulk API 2.0, upsert on `External_Id__c`.
**Status:** design — requires a Salesforce org to execute; not run in CI.

## Governance
- CDEs drive both the SCD2 change hash and the reconciliation hash — one list,
  defined in `config/reconciliation_rules.json`.
- Every mapping row traces to a legacy column or is marked *derived/pipeline*.
- Code→label maps live in reference data, not hard‑coded (lifted out of the
  legacy procedure).
