---
id: financial_risk
name: Financial Risk & Credit Analysis
version: 1.0
embedding_keywords:
  - financial analysis
  - credit risk
  - annual report
  - bokslut
  - revenue
  - balance sheet
  - income statement
  - credit rating
  - payment remarks
  - bankruptcy prediction
  - financial ratios
  - liquidity
  - solvency
  - profitability
  - altman z-score
  - transaction analysis
  - money laundering
  - AML
  - suspicious transaction
  - cash flow
mcps: []
apis:
  - allabolag.se
  - proff.se
skills:
  - financial_statement_analysis
  - credit_assessment
  - bankruptcy_prediction
  - transaction_pattern_analysis
  - aml_screening
  - ratio_analysis
tools:
  - fetch_annual_report
  - calculate_ratios
  - assess_credit_risk
  - analyze_transactions
  - screen_aml
required_context:
  - org_number_or_company_name
always_include: false
author: tangle
---

# Skill: Financial Risk & Credit Analysis

## Purpose
Analyze financial health, detect credit risk, identify suspicious transaction patterns, and screen for AML red flags.

## Domain Knowledge

### Key Financial Ratios
| Ratio | Formula | Healthy Range | What It Measures |
|-------|---------|---------------|------------------|
| Equity ratio | Equity / Total assets | > 30% | Long-term solvency |
| Current ratio | Current assets / Current liabilities | > 1.5 | Short-term liquidity |
| Profit margin | Net profit / Revenue | Industry-dependent | Operational efficiency |
| Debt/Equity | Total liabilities / Equity | < 1.0 | Leverage risk |
| Quick ratio | (Current assets - inventory) / Current liabilities | > 1.0 | Emergency liquidity |

### Bankruptcy Prediction
- **Altman Z-Score** (manufacturing): Z = 1.2A + 1.4B + 3.3C + 0.6D + 1.0E
  - Z > 2.99: Safe
  - 1.81 < Z < 2.99: Grey zone
  - Z < 1.81: Distress zone
- **Key leading indicators:** Negative equity, persistent losses, shrinking revenue, auditor qualifications.

### AML Red Flags in Transactions
- Structuring (just below reporting thresholds, e.g. €9,999)
- Rapid movement through multiple accounts (layering)
- Round-number payments inconsistent with business
- Payments to/from high-risk jurisdictions
- Unexplained third-party payments
- Transactions inconsistent with business profile

### Credit Risk Indicators
| Indicator | Signal |
|-----------|--------|
| Payment remarks | Current/past payment defaults |
| Tax debts | Unpaid taxes — can lead to forced liquidation |
| Negative equity | Liabilities > assets — technical insolvency |
| Auditor resignation | Possible accounting irregularities |
| Repeated losses | Going concern risk |
| Sudden revenue drop | Market loss, customer concentration risk |

## Procedures

### Financial Health Assessment
1. **Collect** — Last 3 annual reports (revenue, profit, equity, assets, liabilities).
2. **Calculate** — Key ratios for each year (equity, current, profit margin, debt/equity).
3. **Trend** — Analyze 3-year trajectory (growing/stable/declining).
4. **Benchmark** — Compare against industry averages (same SNI/NACE code).
5. **Altman** — Calculate Z-score if applicable.
6. **Check** — Payment remarks, tax debts, auditor sign-off.
7. **Score** — Overall financial health: Strong / Satisfactory / Weak / Distressed.

### Transaction Pattern Analysis
1. **Ingest** — Parse transaction logs, bank statements, invoice data.
2. **Volume** — Total inflow/outflow, average transaction size, frequency.
3. **Counterparties** — Identify recurring recipients/senders, geographic distribution.
4. **Anomalies** — Flag: structuring, round numbers, rapid movement, unexpected jurisdictions.
5. **Pattern** — Identify: salary payments, supplier payments, dividends, unusual large transfers.
6. **Report** — Transaction profile, anomaly table, risk score.

## Caveats
- **Lag:** Annual reports are historical (7+ months old by filing).
- **Comparability:** Different accounting standards (K2, K3, IFRS) affect ratios.
- **Private companies:** Limited disclosure requirements — less data available.
- **Not investment advice:** Analysis is for risk assessment, not investment decisions.

## Output Format
```
### Financial Risk: [Company]

#### Financial Summary (3-year)
| Year | Revenue | Profit | Equity | Assets | Margin | Equity Ratio |
|------|---------|--------|--------|--------|--------|--------------|

#### Ratio Analysis
| Ratio | Year 1 | Year 2 | Year 3 | Benchmark | Verdict |
|-------|--------|--------|--------|-----------|---------|

#### Credit & Risk
| Indicator | Status | Source |
|-----------|--------|--------|
| Payment remarks | ... | ... |
| Credit rating | ... | ... |
| Altman Z-score | ... | ... |

#### Overall Assessment
[Strong / Satisfactory / Weak / Distressed] — [Key drivers]
```
