---
id: swedish_public_records
name: Swedish Public Records & Registers
version: 1.0
embedding_keywords:
  - swedish public records
  - offentliga handlingar
  - bolagsverket
  - skatteverket
  - lantmäteriet
  - fastighetsbeteckning
  - folkbokföring
  - konkurs
  - rekonstruktion
  - företagsregister
  - verklig huvudman
  - styrelse
  - revisor
  - årsredovisning
  - betalningsanmärkning
  - kronofogden
  - org.nr
  - personnummer
mcps: []
apis:
  - bolagsverket.se
  - oppetdata.se
  - lantmateriet.se
skills:
  - company_lookup
  - property_lookup
  - bankruptcy_check
  - board_member_trace
  - beneficial_owner_search
tools:
  - search_company
  - search_property
  - check_tax_registration
  - search_board_members
required_context:
  - org_number_or_company_name
always_include: false
author: tangle
---

# Skill: Swedish Public Records & Registers

## Purpose
Query Swedish public authorities to verify company status, trace property ownership, check tax registration, and map corporate networks.

## Domain Knowledge

### Bolagsverket
- All Swedish companies registered: AB, HB, KB, EF, EK.FÖR.
- Public data: name, org.nr, legal form, status, board, CEO, auditor, share capital, verklig huvudman.
- Annual reports (årsredovisning) public for aktiebolag.
- NOT public: real-time financials, detailed share register.

### Skatteverket
- Public for companies: F-skatt status, momsregistrering, employer registration.
- Private: individual tax data.

### Lantmäteriet
- Fastighetsbeteckning: unique property identifier.
- Public: boundaries, area, type, ownership history, easements, mortgages.
- NOT public: current owner's personal details (restricted).

### Kronofogden
- Public: payment remarks (betalningsanmärkningar) for companies.
- Impact: severely affects creditworthiness.

### Key Legal Forms
| Form | Liability | Public Financials |
|------|-----------|-------------------|
| Aktiebolag (AB) | Limited | Yes |
| Enskild firma (EF) | Unlimited | No |
| Handelsbolag (HB) | Unlimited | No |
| Kommanditbolag (KB) | Mixed | No |

## Procedures

### Company Verification
1. **Bolagsverket** — Confirm registration, org.nr, legal form, status.
2. **Board & UBO** — List current board, CEO, auditor, verklig huvudman.
3. **Tax Status** — Check F-skatt, momsregistrering.
4. **Financials** — Fetch latest annual report + summary.
5. **Credit** — Check payment remarks.
6. **Network** — Map related companies via board members' other directorships.

### Property Investigation
1. **Identify** — Fastighetsbeteckning or address.
2. **Lantmäteriet** — Boundaries, area, type, ownership history.
3. **Mortgages** — Check encumbrances, easements.
4. **Owner Context** — Cross-reference with Bolagsverket if company-owned.

## Caveats
- **Privacy:** Swedish GDPR is strict. Stick to company and property data.
- **Timeliness:** Bolagsverket updates may lag 1-2 weeks.
- **Language:** Most registers are in Swedish. Cite original Swedish terms.

## Output Format
```
### Swedish Public Records: [Entity]

#### Company Profile
| Field | Value |
|-------|-------|
| Name | ... |
| Org.nr | ... |
| Legal form | ... |
| Status | ... |

#### Board & Control
| Role | Name | Since |
|------|------|-------|
```
