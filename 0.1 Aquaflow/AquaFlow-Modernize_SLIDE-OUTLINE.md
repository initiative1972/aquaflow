# AquaFlow‑Modernize — Slide Deck Outline (interview showcase)

**Purpose:** an end‑to‑end walkthrough of the AquaFlow‑Modernize portfolio project
for the **Technical Lead – Enterprise Data & Analytics** interview at Yarra Valley
Water (YVW). Designed to be loaded into **Gemini / NotebookLM** to generate the deck.

---

## How to use this with Gemini

1. In Gemini (or NotebookLM), add this file as a source — plus, optionally, the
   repo `README`, `docs/runbook-cutover.md`, `docs/adr/0002-*.md`, and
   `powerbi/semantic-model.md` for richer grounding.
2. Prompt:
   > *"Generate a 16‑slide presentation from this outline. One slide per section.
   > Use the slide title, keep bullets to 4–6 short lines, and put the 'Say this'
   > text into the speaker notes. Clean, corporate, navy/teal palette, minimal
   > icons, no stock photos of people."*
3. Export to Google Slides / PowerPoint and adjust.

**Tone rules (keep these):** honest about synthetic data and what runs vs. what is
design; lead with *judgement and delivery discipline*, not tool name‑drops; the
utility in the story is fictional ("AquaFlow Water"), **not** YVW.

---

## Slide 1 — Title

- **AquaFlow‑Modernize**
- Legacy T‑SQL → Azure Databricks Lakehouse, with automated reconciliation and DataOps
- Henry Yan · Portfolio project for Technical Lead, Enterprise Data & Analytics
- *Built on synthetic data; patterns are production‑grade*

**Say this:** "This is a reference implementation I built to show how I'd lead a
legacy‑to‑cloud migration end to end — the engineering, the reconciliation
assurance, and the delivery discipline. All data is synthetic; the patterns are
the real thing."

---

## Slide 2 — Context: the problem

- A monolithic, **undocumented 3,000‑line T‑SQL stored procedure** generates daily
  billing and land‑development datasets
- Cursors, temp tables, embedded business rules → fragile, slow, high key‑person risk
- Runs on‑prem; the business is moving customer domains to **Salesforce** and
  modern analytics
- Can't be retired until the new platform is **provably equivalent**

**Say this:** "The classic migration trap: a procedure nobody fully understands,
that the business can't switch off because they can't prove a replacement matches
it. That proof problem is the heart of this project."

**Visual:** before/after — tangled SP box vs. clean medallion layers.

---

## Slide 3 — Business case

- **Risk:** single point of failure, no lineage, no tests, audit exposure
- **Cost & performance:** procedural row‑by‑row vs. set‑based distributed compute
- **Strategic:** unlocks the Salesforce customer‑domain transition and self‑service BI
- **Compliance:** regulated billing needs **zero‑discrepancy, evidenced** cutover
- **Outcome sought:** maintainable, testable, automated platform — *trusted* reporting

**Say this:** "The business case isn't 'cloud is nice'. It's retiring key‑person
risk and audit exposure, enabling the Salesforce move, and — critically — being
able to *evidence* that the migration is correct, not just assert it."

---

## Slide 4 — Solution overview (architecture)

- **Ingest:** Azure Data Factory, metadata‑driven, into ADLS Gen2
- **Lakehouse:** Databricks medallion — Bronze (raw) → Silver (SCD2) → Gold (marts)
- **Assure:** automated dual‑run reconciliation gate (circuit breaker)
- **Serve:** Power BI semantic model + Salesforce‑ready outbound
- **Automate:** GitHub Actions CI, Bicep IaC, Dev/SIT/UAT/Prod

**Say this:** "Source to serving on one slide. The piece most migrations
under‑invest in is the reconciliation gate in the middle — that's where I put the
emphasis."

**Visual:** the end‑to‑end pipeline diagram from the README.

---

## Slide 5 — Data sources & structure

- **Source:** legacy SQL Server — `Account`, `Property`, `Billing`, plus temp tables
- **Bronze:** append‑only Delta via **Auto Loader**, schema inference + evolution,
  audit columns (`ingestion_ts`, `source_file`) added, raw history preserved
- **Silver:** cleansed, deduped, conformed; **SCD2** dimensions
- **Gold:** `Customer360`, `FactBilling` (grain: account × day) — BI/Salesforce ready
- Each layer has one job; business logic only appears in Silver/Gold

**Say this:** "Bronze is immutable raw — I never transform there, so I can always
replay. Audit columns are added at Bronze and deliberately excluded from
reconciliation hashing later, so pipeline timing can't fake a mismatch."

---

## Slide 6 — Data modeling & mapping

- **Star schema:** `FactBilling` + `DimCustomer`/`DimProperty` (SCD2), `DimDate`, `DimTariff`
- **SCD Type 2:** `effective_start` / `effective_end` / `is_current` + CDE hash
- **Source‑to‑target mapping (STTM):** every target column traces to a legacy column
  or is marked derived; code→label maps lifted into reference data
- **Salesforce outbound:** `Customer360` → Salesforce objects, upsert on external id
- **CDEs** drive both the SCD2 change hash *and* the reconciliation hash — one list

**Say this:** "A documented STTM is a lead artefact — it's how you make a migration
reviewable. And I define Critical Data Elements once; the same list drives change
detection and reconciliation, so there's no drift between them."

**Visual:** small STTM table excerpt + star‑schema thumbnail.

---

## Slide 7 — Reverse engineering approach

- **Deconstruct:** map T‑SQL dependencies — temp tables, cursors, final `INSERT`s
- **Refactor, don't lift‑and‑shift:** cursors/`WHILE` → set‑based PySpark, window
  functions, broadcast joins
- **Isolate business rules:** hard‑coded values → reference/config, not buried in code
- **Accelerate with AI, verify with humans:** a Gemini‑assisted parser *proposes*
  PySpark per block; every block is flagged for engineer review
- Honest framing: an **accelerator**, not an automatic transpiler

**Say this:** "I use AI to cut the reverse‑engineering time, but I never treat the
output as trusted — it's human‑in‑the‑loop. Over‑trusting an LLM translation is
exactly the failure mode this project argues against."

---

## Slide 8 — Data transformation: SCD2 (a correctness story)

- Silver merge replaces legacy cursor loops with a **Delta MERGE**
- The gotcha: "merge then append all" **duplicates unchanged rows** as a second
  `is_current = true` version — silent until a count or join doubles
- Fixed with the **two‑step / null‑merge‑key** pattern: expire changed, insert
  new/changed, leave unchanged untouched
- Locked in by a test: `test_rerun_unchanged_no_duplicates`
- Decision recorded in **ADR‑0002**

**Say this:** "I want to show a specific gotcha because it's the kind of thing that
separates 'wrote some PySpark' from 'ran a migration'. The naive SCD2 merge
duplicates current rows. I fixed it, wrote a test that fails if anyone reintroduces
it, and recorded why in an ADR."

**Visual:** two tiny tables — buggy (duplicate current) vs. correct (one current + expired).

---

## Slide 9 — Ingestion → reconciliation / migration

- **Dual‑run:** legacy and modern run in parallel on the same inputs
- **Macro gate:** compare `SUM(total_billed)` and counts by date — cheap gross check
- **Micro gate:** **SHA‑256 row hash** over CDEs, full‑outer join → catches changed
  values, missing rows, extra rows
- **Circuit breaker:** drift > tolerance → pipeline fails, Gold/BI never refreshes
- **Equivalence within tolerance**, evidenced and logged — not "trust me"

**Say this:** "This is the slide I'd dwell on. Reconciliation isn't an afterthought
— it's an automated gatekeeper between Silver and Gold. If drift exceeds tolerance
the pipeline deliberately fails, so corrupted data can't reach the business."

**Visual:** reconciliation gate with PASS/BREACH branch.

---

## Slide 10 — Cutover & stakeholder leadership *(the lead slide)*

- **Go/No‑Go gate** per cycle: drift, macro variance, DQ suite, late‑arrival backlog
- **The 8:00 AM scenario:** breaker trips; exec dashboard due 8:30
  - Contain → assess → **fallback to last validated snapshot** (Delta time travel)
  - Lead the comms: "showing verified data as of…", accuracy over speed, ETA
- **Rollback:** repoint semantic layer to prior Gold version in minutes
- Roles, settlement windows (T+1), late/out‑of‑sequence handling — in the runbook

**Say this:** "A tech lead is judged on the bad morning, not the happy path. I wrote
a cutover runbook with a worked 8am failure: what the breaker does, how we fall
back to a trusted snapshot, and exactly how I'd communicate to executives. That's
the difference between an engineer and a lead."

---

## Slide 11 — CI/CD & engineering discipline

- **Logic in a tested package; notebooks stay thin** — same code runs in CI and on
  Databricks (no parallel re‑implementation)
- **GitHub Actions:** flake8 → **pytest on a local Spark + Delta session** → green
  badge is *real*
- Tests cover the SCD2 no‑duplicate guarantee and the reconciliation breaker
- **IaC** (Bicep) + Databricks Asset Bundles promoted **Dev → SIT → UAT → Prod**
- **ADRs** record the decisions, not just the code

**Say this:** "My CI badge is honest — it only runs what genuinely runs. The pure
transforms are unit‑tested on a local Spark session on every PR, which is why a
green check actually means the production path is correct."

---

## Slide 12 — Power BI visualisation

- **Star schema** semantic model over Gold; `DimDate` marked for time intelligence
- **Measures:** billing, YoY/MTD/YTD, and **data‑quality KPIs** —
  `Reconciliation Drift %`, `Reconciliation Status` (PASS/BREACH), `Last Refresh`
- **Governance:** row‑level security by region, **certified dataset**, sensitivity label
- **Performance:** import/Direct Lake, incremental refresh by `bill_date`, no snowflaking
- Trust signals on the report cover — consumers see the data passed the gate

**Say this:** "I surface the reconciliation status *inside* the report. The business
doesn't just get numbers — they get a visible signal that the data passed the gate
and when it last refreshed. That closes the loop from pipeline to consumer."

**Visual:** mock report cover with a green PASS tile + Last Refresh.

---

## Slide 13 — How this maps to the YVW role

| JD requirement | Evidence |
| --- | --- |
| Reverse‑engineer undocumented legacy ETL/SPs | Deconstruct→refactor→isolate; AI accelerator (HITL) |
| Azure lakehouse, scalable pipelines, data products | Medallion, Delta, thin notebooks + tested transforms |
| Data modelling (SCD2, star, semantic layer) | SCD2 merge, star schema, Power BI model |
| Advanced Power BI (DAX, governance) | Measures, RLS, certified dataset, incremental refresh |
| Reconciliation / validation / fit for consumption | Dual‑run gate, circuit breaker, logged evidence |
| DevOps / CI/CD across environments | GitHub Actions, Bicep, Dev/SIT/UAT/Prod |
| Technical leadership | ADRs, cutover runbook, STTM, go/no‑go |

**Say this:** "Every essential in your ad has a concrete artefact behind it — not a
claim, something you can open."

---

## Slide 14 — Honest scope

- **Runs & tested in CI:** Silver SCD2, Gold logic, reconciliation, on local Spark
- **Design artefacts (need Azure/Salesforce/Power BI):** ADF, Bicep, Auto Loader,
  Salesforce outbound, the `.pbix`
- **All data synthetic;** utility is fictional; no employer/customer data
- Scale shown by **pattern**, not a billion‑row benchmark

**Say this:** "I'm deliberately clear about what executes versus what's designed.
That honesty is the point — it's how I'd report status on a real programme too."

---

## Slide 15 — Learnings

- Reconciliation is the migration — build the gate first, not last
- The dangerous bugs are **silent** (duplicate current rows); tests must encode the
  gotchas, not just the happy path
- Keep business logic in a **tested package**; notebooks are orchestration only
- AI is a powerful **accelerator** for reverse engineering — with human verification
- Lead artefacts (ADRs, runbook, STTM) make a migration *reviewable* and *handover‑safe*

**Say this:** "If I take one thing into the YVW role: prove equivalence early and
automatically, and write down the decisions so the team can inherit them."

---

## Slide 16 — Close

- End‑to‑end: legacy SP → governed lakehouse → assured, trusted, automated serving
- Repo is inspectable; CI is genuinely green; decisions are documented
- *"Happy to open any file you like — including the least flattering one."*
- Thank you / questions

**Say this:** "That's the walkthrough. The repo is public and the CI is real —
I'd genuinely welcome you opening any part of it, including the parts I'd still
improve."

---

### Appendix slides (optional, if asked)
- A1: SCD2 two‑step merge code + the test
- A2: Reconciliation function (hash + full‑outer + breaker)
- A3: ADR‑0002 summary (decision / consequences / alternatives)
- A4: Cutover runbook — go/no‑go table and the exec comms template
