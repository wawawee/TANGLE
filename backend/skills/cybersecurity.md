---
id: cybersecurity
name: Cybersecurity & Threat Intelligence
version: 1.0
embedding_keywords:
  - cybersecurity
  - threat intelligence
  - vulnerability
  - CVE
  - malware
  - IOC
  - indicator of compromise
  - phishing
  - ransomware
  - penetration test
  - exploit
  - zero day
  - APT
  - threat actor
  - dark web
  - CISA KEV
  - EPSS
  - CVSS
  - nvd
mcps: []
apis:
  - nvd.nist.gov
  - cve.mitre.org
  - abuseipdb.com
skills:
  - vulnerability_assessment
  - ioc_analysis
  - threat_actor_profiling
  - infrastructure_mapping
  - breach_indicators
tools:
  - search_cve
  - check_ip_reputation
  - search_exploit_db
  - map_infrastructure
  - analyze_threat_actor
required_context:
  - target_ip_domain_or_cve
always_include: false
author: tangle
---

# Skill: Cybersecurity & Threat Intelligence

## Purpose
Assess security posture, analyze threats, investigate indicators of compromise (IOCs), and profile threat actors.

## Domain Knowledge

### Vulnerability Management
- **CVE:** Unique ID for known vulnerabilities (CVE-YYYY-NNNNN).
- **CVSS v3.1:** Critical (9.0-10.0), High (7.0-8.9), Medium (4.0-6.9), Low (0.1-3.9).
- **EPSS:** Exploit prediction score (0-1) — probability of exploitation within 30 days.
- **CISA KEV:** Known Exploited Vulnerabilities catalog — federal mandate to patch.

### Indicator of Compromise (IOC) Types
- IP addresses, domains, URLs, file hashes (MD5/SHA1/SHA256), email addresses.
- Enrichment: VirusTotal, AbuseIPDB, GreyNoise, AlienVault OTX.
- Context: first seen, last seen, associated campaigns, geolocation, ASN.

### Threat Actor Frameworks
- **MITRE ATT&CK:** Tactics, Techniques, Procedures (TTPs).
- **Sectors:** Nation-state (APT29, Lazarus), cybercrime (LockBit, Cl0p), hacktivist.
- **Attribution:** TTP overlap, infrastructure overlap, language artifacts, timing.

## Procedures

### Vulnerability Assessment
1. **Identify** — Software + version, or CVE ID.
2. **NVD** — CVSS, EPSS, CISA KEV status.
3. **Exploitability** — Network/local, complexity, privileges required.
4. **Exploit available** — Check Metasploit, Exploit-DB.
5. **Recommend** — Patch, workaround, mitigate, or accept risk.

### IOC Investigation
1. **Collect** — IPs, domains, hashes, URLs.
2. **Enrich** — VirusTotal (hashes), AbuseIPDB (IPs), WHOIS (domains).
3. **Correlate** — Group by campaign, timeline, infrastructure.
4. **Assess** — Malicious / suspicious / benign — with confidence.
5. **Context** — Link to known threat actors or campaigns.

## Caveats
- **Attribution is hard:** IP geolocation can be spoofed. TTP overlap is suggestive.
- **False positives:** Verify with multiple sources.
- **Legal:** Active scanning or exploitation without authorization is illegal.
- **Stale IOCs:** Threat actors rotate infrastructure rapidly (>30 days old may be stale).

## Output Format
```
### Cybersecurity Analysis: [Target/IOC/CVE]

#### Vulnerability Summary
| CVE | CVSS | EPSS | CISA KEV | Exploit Available | Rec |
|-----|------|------|----------|-------------------|-----|

#### IOCs
| IOC | Type | Reputation | Campaign | Confidence |
|-----|------|------------|----------|------------|

#### Threat Actor (if identified)
| Group | Confidence | TTPs | Targets |
|-------|------------|------|---------|

#### Recommendations
1. Immediate action
2. Short-term fix
3. Long-term hardening
```
