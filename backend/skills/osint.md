---
id: osint
name: Open Source Intelligence
version: 1.0
embedding_keywords:
  - osint
  - open source intelligence
  - person lookup
  - social media
  - digital footprint
  - username search
  - email trace
  - phone lookup
  - domain investigation
  - whois
  - reverse image search
  - geolocation
  - breach analysis
mcps:
  - sherlock-mcp
apis:
  - haveibeenpwned
  - hunter.io
skills:
  - person_lookup
  - social_media_mapping
  - email_trace
  - username_correlation
  - domain_investigation
  - breach_analysis
tools:
  - search_username
  - search_email
  - map_social_graph
  - check_breach
required_context:
  - target_identifier
always_include: false
author: tangle
---

# Skill: Open Source Intelligence (OSINT)

## Purpose
Map the digital footprint of a person, organization, or online identity using publicly available data.

## Domain Knowledge
- A person can be identified by: full name, email, username, phone number, photo, IP address.
- Cross-platform username reuse is the #1 correlation vector.
- Profile metadata (bio, location, join date, connections) often reveals more than posts.
- Breach data reveals service associations and signup dates. Never report raw passwords.
- WHOIS history can reveal registrant details before GDPR/privacy redaction.

## Procedures

### Person Footprint Mapping
1. **Identify** — Determine the strongest available identifier (email > username > phone > name).
2. **Expand** — Search for accounts across platforms.
3. **Correlate** — Cross-reference usernames, profile photos, bio text, locations.
4. **Verify** — Confirm at least 2 independent sources before marking "confirmed."
5. **Report** — Present findings with confidence levels and source URLs.

### Breach Analysis
1. Check email against HaveIBeenPwned.
2. Note: service name, breach date, data classes exposed (no raw passwords).
3. Report aggregate exposure risk (low/medium/high).

### Domain Investigation
1. Run WHOIS lookup (current + historical).
2. Check DNS records (A, MX, TXT, NS).
3. Check certificate transparency logs (crt.sh) for subdomains.

## Caveats
- **Privacy laws** (GDPR, CCPA) restrict what you can collect. Stay within public data only.
- **False positives** are common with common names. Disambiguate with location or context.
- **Outdated data** — social media profiles are often abandoned. Check "last active" dates.

## Output Format
```
### OSINT Analysis: [Target]
**Identifier Used:** [email/username/phone]
**Platforms Found:** [N] confirmed, [M] possible

#### Confirmed Accounts
| Platform | Username | Confidence |
|----------|----------|------------|
```
