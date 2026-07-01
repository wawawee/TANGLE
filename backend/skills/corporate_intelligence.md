---
id: corporate_intelligence
name: Corporate Intelligence & Due Diligence
version: 1.0
embedding_keywords:
  - corporate intelligence
  - due diligence
  - company investigation
  - ownership structure
  - beneficial owner
  - board network
  - corporate tree
  - subsidiary
  - holding company
  - shell company
  - offshore
  - ultimate beneficial owner
  - UBO
  - corporate registry
  - business verification
mcps: []
apis:
  - opencorporates.com
  - allabolag.se
skills:
  - company_verification
  - ownership_mapping
  - beneficial_owner_tracing
  - corporate_network_analysis
  - shell_company_detection
  - cross_border_entity_search
tools:
  - trace_ownership_chain
  - detect_shell_indicators
  - map_corporate_tree
  - search_director_network
required_context:
  - company_name_or_org_number
always_include: false
author: tangle
---

# Skill: Corporate Intelligence & Due Diligence

## Purpose
Investigate corporate entities, map ownership structures, trace ultimate beneficial owners, and detect red flags across jurisdictions.

## Domain Knowledge

### Corporate Structures
- **Legal forms:** AB (Sweden), Ltd (UK), GmbH (Germany), LLC (US), SA (Switzerland), JSC (UAE).
- **Ownership layers:** Direct shareholder → holding company → trust → ultimate beneficiary.
- **Common red flags:**
  - Circular ownership (A owns B, B owns A)
  - Nominee directors / shareholders
  - Registered address = mass registration address (WeWork, virtual office)
  - Frequent changes in board composition
  - Dormant companies with sudden activity
  - Jurisdictions known for secrecy (Panama, BVI, Seychelles, Delaware)

### Ultimate Beneficial Owner (UBO)
- Definition: individual who ultimately owns or controls >25% of shares/votes.
- Tracing chain: follow each ownership layer until you hit a natural person.
- If a trust or foundation: identify beneficiaries and settlors.
- If nominee: identify the nominator.

### Red Flag Indicators
| Indicator | Risk Level | Description |
|-----------|------------|-------------|
| Shell company | High | No physical presence, no employees, registered at mass address |
| Offshore jurisdiction | Medium-High | BVI, Panama, Cayman, Seychelles, Marshall Islands |
| PEP involvement | High | Politically Exposed Person as owner/board member |
| Recent incorporation | Low-Medium | Company < 6 months old seeking significant transactions |
| Complex ownership | Medium | >3 layers of ownership, especially cross-border |
| Negative press | Medium | Sanctions, litigation, regulatory actions |

## Procedures

### Ownership Chain Tracing
1. **Start** — Identify target company in home registry.
2. **Direct** — List all direct shareholders from registry.
3. **Layer 2** — For each corporate shareholder, find its home registry and extract its shareholders.
4. **Layer N** — Repeat until you reach natural persons (or dead end: trust, bearer shares).
5. **UBO** — Identify individuals with >25% ultimate control.
6. **Network** — Map all entities in the chain, flag jurisdictions and red flags.

### Shell Company Detection
1. Check registered address — is it a virtual office / mass registration?
2. Check number of employees — zero employees = shell indicator.
3. Check financials — minimal revenue vs. large assets.
4. Check board — nominee directors (same names across many companies).
5. Check age — recently registered for purpose of a specific transaction.
6. Report — shell likelihood score + evidence.

## Caveats
- **Registry quality varies** — Some countries have no public UBO register.
- **Trusts are opaque** — Beneficiaries of discretionary trusts may be unknowable.
- **Bearer shares** — Ownership follows physical certificate; effectively untraceable.
- **Not legal advice** — Corporate intelligence supports decision-making, not legal conclusions.

## Output Format
```
### Corporate Intelligence: [Company]

#### Corporate Profile
| Field | Value |
|-------|-------|
| Legal name | ... |
| Org.nr / Reg. ID | ... |
| Jurisdiction | ... |
| Legal form | ... |
| Status | Active / Dormant / Liquidated |
| Incorporation date | ... |

#### Ownership Structure
```
[UBO Name] → [Holding Co] → [Target]
       ↓
[Second UBO] → [Trust] ──→ [Target]
```

#### Red Flags
| Flag | Severity | Detail |
|------|----------|--------|
| ... | High/Med/Low | ... |

#### Overall Risk Assessment
[Summary with key drivers and confidence]
```
