---
id: synthesis_reporting
name: Synthesis & Structured Reporting
version: 1.0
embedding_keywords:
  - synthesis
  - reporting
  - due diligence report
  - investigation report
  - structured report
  - findings
  - recommendations
  - confidence matrix
  - risk scoring
  - executive summary
  - source appendix
  - report template
mcps: []
apis: []
skills:
  - report_generation
  - finding_synthesis
  - risk_scoring
  - recommendation_prioritization
  - source_management
tools: []
required_context: []
always_include: true
author: tangle
---

# Skill: Synthesis & Structured Reporting

## Purpose
Structure all findings into a professional due diligence or investigation report with clear findings, confidence scoring, risk assessment, and actionable recommendations.

## Domain Knowledge

### Report Structure
Every investigation report should follow this hierarchy:
1. **Executive Summary** — The most important 2-3 sentences. Assume this is all the reader will read.
2. **Key Findings** — Ranked by importance, each with evidence and confidence score.
3. **Entity Profile** — Verified identity information.
4. **Domain Analysis** — Organized by active skill domain (corporate, financial, legal, etc.).
5. **Risk Assessment** — Overall risk score with key drivers.
6. **Recommendations** — Prioritized, actionable next steps.
7. **Appendix** — Sources, methodology, confidence matrix.

### Confidence Scoring
| Score | Meaning | Evidence Required |
|-------|---------|-------------------|
| High | Highly likely true | Multiple independent primary sources, or single authoritative source |
| Medium | Likely true | Single source, or multiple secondary sources with alignment |
| Low | Possible but unverified | Single secondary source, inference, or unverifiable claim |
| Insufficient | Cannot assess | No data available, contradictory evidence |

### Risk Scoring Framework
| Level | Meaning | Implication |
|-------|---------|-------------|
| Critical | Immediate action required | Proceed only with board-level sign-off |
| High | Significant concerns | Enhanced due diligence before proceeding |
| Medium | Notable issues | Standard due diligence, monitor closely |
| Low | Minor or no concerns | Proceed with standard monitoring |

### Source Management
- Tag every source with: name, URL (if applicable), date accessed, reliability (primary/secondary/unverified).
- Note any conflicts between sources and how they were resolved.
- Flag sources that are potentially biased (industry-funded, political affiliation).

## Procedures

### Building the Report
1. **Aggregate** — Collect all findings from every phase and skill.
2. **Prioritize** — Rank findings by: risk severity, financial materiality, legal implications.
3. **Synthesize** — Connect related findings across domains. Look for patterns.
4. **Score** — Assign confidence to each finding.
5. **Assess** — Overall risk level with key drivers.
6. **Recommend** — 3-5 actionable recommendations, prioritized.
7. **Format** — Professional markdown with clear visual structure.

## Output Format
```
# Due Diligence Report: [Entity]

## Executive Summary
[2-3 sentences]

## Key Findings
1. [Critical finding] (confidence: high)
2. [Important finding] (confidence: medium)
...

## Risk Assessment
**Overall Risk:** [Critical/High/Medium/Low]
**Key Drivers:** [Top 3 risk factors]

## Recommendations
1. **Immediate:** [Action with timeline]
2. **Short-term:** [Action with timeline]
3. **Ongoing:** [Action with timeline]

## Confidence Matrix
| Finding | Confidence | Sources | Rationale |
|---------|------------|---------|-----------|

## Sources
1. [Source name] — [URL] — [Type]
```
