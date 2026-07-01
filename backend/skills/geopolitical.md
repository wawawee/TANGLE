---
id: geopolitical
name: Geopolitical & Market Risk
version: 1.0
embedding_keywords:
  - geopolitical risk
  - sanctions
  - country risk
  - political risk
  - market analysis
  - industry analysis
  - trade war
  - embargo
  - export control
  - corruption index
  - world bank
  - IMF
  - country profile
  - political stability
  - regulatory risk
  - emerging market
  - jurisdiction risk
mcps: []
apis:
  - worldbank.org
  - transparency.org
skills:
  - country_risk_assessment
  - sanctions_regime_analysis
  - industry_trend_analysis
  - political_stability_evaluation
  - market_entry_risk
tools:
  - assess_country_risk
  - analyze_trade_barriers
  - evaluate_political_stability
  - benchmark_corruption
required_context:
  - country_or_region
always_include: false
author: tangle
---

# Skill: Geopolitical & Market Risk

## Purpose
Assess country-level risk, political stability, sanctions exposure, and market conditions relevant to an entity or investment target.

## Domain Knowledge

### Country Risk Dimensions
| Dimension | Description | Key Sources |
|-----------|-------------|-------------|
| Political stability | Government stability, conflict risk, rule of law | World Bank WGI, Economist Intelligence Unit |
| Corruption | Perception of corruption, bribery risks | Transparency International CPI |
| Regulatory quality | Ease of doing business, bureaucratic quality | World Bank, Heritage Foundation |
| Economic stability | Inflation, debt, currency risk, growth trajectory | IMF, World Bank |
| Sanctions exposure | OFAC/EU/UN sanctions regime applicability | OFAC, EU Sanctions Map |
| Legal system | Contract enforcement, property rights, court independence | World Justice Project |

### Key Indicators
- **Corruption Perceptions Index (CPI):** 0 (highly corrupt) to 100 (very clean).
- **Worldwide Governance Indicators (WGI):** Percentile rank (0-100) for voice/accountability, political stability, government effectiveness, regulatory quality, rule of law, corruption control.
- **Ease of Doing Business:** Rank based on business registration, permits, taxes, contract enforcement (discontinued 2021 but still used).
- **GDP growth:** Real GDP growth rate, inflation, unemployment.

### Trade & Investment Risks
- **Export controls:** US EAR, EU Dual-Use Regulation — restrict exports of sensitive technology.
- **Investment screening:** CFIUS (US), FIRRMA, EU FDI Screening Regulation.
- **Local content requirements:** Mandated local sourcing in some jurisdictions.
- **Currency controls:** Restrictions on capital movement, repatriation of profits.

### Dubai/UAE Specific Context
- **Free zones:** DIFC, ADGM, DMCC, JAFZA — each has its own regulatory framework.
- **DIFC:** English common law, independent courts, 0% corporate tax (pre-2023), no currency controls.
- **ADGM:** Same characteristics, with additional Fintech and asset management frameworks.
- **Federal vs. local:** UAE federal law applies, but free zones have their own civil/commercial codes.
- **AML/CFT:** UAE Central Bank supervision, increasingly stringent after FATF grey-listing (2022-2024).

## Procedures

### Country Risk Assessment
1. **Profile** — Political system, stability history, current leadership.
2. **Economy** — GDP, inflation, currency stability, sovereign debt rating.
3. **Governance** — Corruption index, rule of law, regulatory quality.
4. **Sanctions** — Check OFAC/EU/UN sanctions status.
5. **Trade** — Tariffs, export controls, investment restrictions.
6. **Risk score** — Weighted composite of all dimensions.

### Sanctions Exposure Analysis
1. Identify all jurisdictions involved (target domicile, ownership chain, transaction route).
2. Map sanctions regimes applicable to each jurisdiction.
3. Check for sectoral sanctions (finance, energy, defense, technology).
4. Check for targeted individuals/entities in ownership chain.
5. Assess risk of secondary sanctions (US extraterritorial reach).

## Caveats
- **Static data:** Country risk profiles change slowly but can shift rapidly (coup, sanctions).
- **Averaging hides variance:** National averages mask regional differences (e.g., Dubai vs. rural UAE).
- **Bias in sources:** World Bank data reflects government-reported statistics. Cross-reference.
- **Not predictive:** Risk assessment is directional, not a forecast.

## Output Format
```
### Geopolitical Risk: [Country/Region]

#### Country Profile
| Indicator | Value | Source |
|-----------|-------|--------|
| Political stability | ... percentile | WGI |
| Corruption (CPI) | .../100 | Transparency Intl |
| Regulatory quality | ... percentile | WGI |
| Sovereign rating | ... | S&P/Moody's/Fitch |

#### Sanctions Exposure
| Regime | Status | Detail |
|--------|--------|--------|

#### Market Risk Factors
| Risk | Severity | Detail |
|------|----------|--------|

#### Overall Country Risk
[Low / Medium / High / Critical]
```
