---
id: legal_compliance
name: Legal & Compliance Risk
version: 1.0
embedding_keywords:
  - legal compliance
  - AML
  - KYC
  - sanctions
  - OFAC
  - EU sanctions
  - UN sanctions
  - regulatory
  - regulation
  - court records
  - litigation
  - bankruptcy
  - insolvency
  - regulatory filing
  - compliance check
  - watchlist
  - PEP
  - politically exposed person
  - adverse media
  - embargo
mcps: []
apis:
  - ofac.treasury.gov
  - sanctionssearch.ofac.treas.gov
skills:
  - sanctions_screening
  - pep_check
  - adverse_media_search
  - litigation_history
  - regulatory_compliance_assessment
  - bankruptcy_search
tools:
  - screen_sanctions
  - check_pep_status
  - search_litigation
  - check_regulatory_status
  - search_bankruptcy
required_context:
  - entity_name_or_identifier
always_include: false
author: tangle
---

# Skill: Legal & Compliance Risk

## Purpose
Screen entities against sanctions lists, identify PEP status, search litigation history, and assess regulatory compliance risk.

## Domain Knowledge

### Sanctions Regimes
- **OFAC (US):** SDN List, CAPTA List, Sectoral Sanctions. Comprehensive Iran, North Korea, Syria, Russia/Crimea, Venezuela.
- **EU Sanctions:** Consolidated list of persons and entities. Russia packages 1-14+, Belarus, Iran, Syria.
- **UN Sanctions:** Consolidated list from Security Council resolutions.
- **UK Sanctions:** OFSI consolidated list (post-Brexit independent regime).
- **Key point:** OFAC has extraterritorial reach (US dollar transactions). EU sanctions apply within EU jurisdiction.

### Politically Exposed Persons (PEP)
- Definition: individuals entrusted with prominent public functions (head of state, minister, judge, general, ambassador, senior SOE executive).
- **Categories:** Foreign PEP, Domestic PEP, International organization PEP.
- **Family & associates:** Close associates and family members are also considered higher risk.
- **Mitigation:** Being a PEP does not mean criminal — enhanced due diligence required.

### Adverse Media
- Categories: criminal activity, fraud, corruption, money laundering, terrorist financing, sanctions violations, regulatory actions.
- Weight: regulatory actions and criminal charges > allegations and rumors.
- Context: distinguish confirmed (court ruling, regulatory fine) from alleged (news report, lawsuit).

### Bankruptcy & Insolvency
- Types: liquidation (konkurs), reconstruction (företagsrekonstruktion), composition (ackordsförhandling).
- Warning signs: payment remarks, tax debts, negative equity, board resignations.

## Procedures

### Sanctions & PEP Screening
1. **Identify** — Entity name, jurisdiction, ownership structure.
2. **Screen** — Check name against OFAC SDN, EU consolidated, UN lists.
3. **Fuzzy match** — Account for transliteration variants, misspellings, DOB mismatches.
4. **PEP** — Check if individual holds or has held prominent public function.
5. **Context** — If partial match, assess: name commonness, jurisdiction alignment, date of birth match.
6. **Report** — Match status (exact / fuzzy / no match), list details, risk level.

### Litigation & Regulatory History
1. **Search** — Court records in relevant jurisdictions.
2. **Filter** — Civil vs criminal, plaintiff vs defendant, outcome.
3. **Regulatory** — Check actions by financial regulators, competition authorities, data protection agencies.
4. **Adverse media** — Search news databases for negative coverage.
5. **Assess** — Pattern of behavior (one-off vs systemic), severity, recency.

## Caveats
- **False positives** are common with common names. Always verify with additional identifiers (DOB, jurisdiction).
- **Sanctions lists change rapidly** — check timeliness of your source data.
- **PEP status is not permanent** — typically 12-18 months after leaving office.
- **Adverse media is not evidence** — distinguish confirmed from alleged.
- **Jurisdiction-specific** — Each country has its own AML/CFT framework.

## Output Format
```
### Compliance Screening: [Entity]

#### Sanctions
| List | Status | Match Type | Detail |
|------|--------|------------|--------|
| OFAC SDN | Clean / Match | Exact / Fuzzy | ... |
| EU Consolidated | Clean / Match | Exact / Fuzzy | ... |
| UN Consolidated | Clean / Match | Exact / Fuzzy | ... |

#### PEP Status
| Category | Status | Detail |
|----------|--------|--------|
| Foreign PEP | Yes / No | ... |
| Domestic PEP | Yes / No | ... |

#### Litigation & Adverse Media
| Type | Date | Status | Detail |
|------|------|--------|--------|
| ... | ... | ... | ... |

#### Risk Assessment
[Low / Medium / High / Critical] — [Key drivers]
```
