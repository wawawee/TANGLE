---
id: blockchain
name: Blockchain & Crypto Asset Analysis
version: 1.0
embedding_keywords:
  - blockchain
  - solana
  - ethereum
  - bitcoin
  - crypto
  - wallet
  - transaction
  - defi
  - smart contract
  - token
  - nft
  - on-chain
  - chain analysis
  - wallet profiling
  - mixer
  - bridge
  - crypto tracing
  - helius
  - rpc
mcps: []
apis:
  - helius.dev
  - solscan.io
  - etherscan.io
skills:
  - transaction_analysis
  - wallet_profiling
  - token_verification
  - defi_protocol_analysis
  - crypto_tracing
tools:
  - get_transaction
  - get_account_info
  - get_token_accounts
  - trace_token_flow
  - analyze_wallet
required_context:
  - wallet_address_or_tx_signature
always_include: false
author: tangle
---

# Skill: Blockchain & Crypto Asset Analysis

## Purpose
Analyze on-chain data to trace transactions, profile wallets, verify token legitimacy, and identify suspicious patterns across Solana, Ethereum, and Bitcoin.

## Domain Knowledge

### Solana Specifics
- **Address:** Base58-encoded 32-44 chars. Transaction has one or more instructions targeting programs.
- **Programs:** System Program (transfers), Token Program (SPL), Associated Token Account, Raydium, Orca, Jupiter.
- **RPC:** Helius recommended. Public RPC rate-limited.
- **Rent:** ~0.002039 SOL minimum balance.

### Ethereum Specifics
- **Address:** 42-char hex starting with `0x`.
- **Standards:** ERC-20 (tokens), ERC-721/1155 (NFTs).
- **Explorer:** Etherscan (API key for heavy usage).

### Common Red Flags
- **Mixers:** Tornado Cash — large inflow followed by distributed outflows.
- **Bridging:** Wormhole, LayerZero — moving assets to obfuscate trail.
- **Pump & Dump:** Rapid creation → liquidity add → massive buy → dump.
- **Rug pull:** Liquidity removed by creator (check LP token burn/lock).
- **Wash trading:** Fake volume on low-cap tokens.
- **MEV/Sandwich:** Frontrunning on DEX swaps.

## Procedures

### Wallet Profiling
1. **Identify** — Confirm address format (Solana/Ethereum/Bitcoin).
2. **Balance** — Native + token balances.
3. **History** — Last 50-100 transactions (time, status, fee, counterparties).
4. **Counterparties** — Map frequent interactors: exchanges, DEXs, known scams, mixers.
5. **Risk flags** — Mixer interaction, sanctions, known scam contracts, unusual velocity.
6. **Report** — Wallet summary, activity pattern, risk assessment.

### Transaction Deep-Dive
1. **Fetch** — Transaction details: block time, fee, status, logs.
2. **Parse** — Decode instructions (transfer, swap, mint, burn).
3. **Trace** — Follow token flow: sender → intermediate → receiver.
4. **Context** — Identify programs (DEX, lending, mixer, bridge).
5. **Anomaly** — Failed TX with high fee (MEV), multi-hop swaps, unusual amounts.
6. **Report** — Flow diagram, instruction breakdown, risk flags.

### Token Verification
1. **Metadata** — Name, symbol, decimals, supply (on-chain or Metaplex).
2. **Creator** — Check creator wallet history (other tokens created?).
3. **Liquidity** — DEX pools: locked or not? How much?
4. **Holders** — Top 10 > 50% = high risk.
5. **Age** — < 7 days = extreme risk.
6. **Social** — Cross-reference with CoinMarketCap, CoinGecko.

## Caveats
- **Pseudonymity:** On-chain data is public but addresses are pseudonymous.
- **Reorg risk:** Recent transactions can be reverted (< 32 Solana slots).
- **Fake volume:** Volume ≠ legitimacy on low-cap tokens.
- **Not financial advice:** Token analysis is for risk assessment only.

## Output Format
```
### Blockchain Analysis: [Address/TX]

#### Wallet Profile
| Field | Value |
|-------|-------|
| Network | Solana / Ethereum / Bitcoin |
| Type | Wallet / Contract / Program |
| Balance | ... |
| First TX | ... |

#### Risk Flags
| Flag | Severity | Evidence |
|------|----------|----------|

#### Assessment
[Summary with confidence]
```
