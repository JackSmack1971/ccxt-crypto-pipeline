# Tier 0 — Universal DEX Aggregators

Load this only when the task touches DexScreener, GeckoTerminal, or DefiLlama ingestion. Snapshot: September 2026. Current official provider docs supersede this snapshot when verified.

## Capability routing

| Need | Primary researched route | Do not substitute |
|---|---|---|
| Strict/new-pool discovery | GeckoTerminal `new_pools` | DexScreener profiles/boosts are promoted/updated-token signals, not a true newest-pairs feed |
| DEX OHLCV/candles | GeckoTerminal OHLCV | DexScreener has no candle endpoint |
| Pair/token snapshot/search | DexScreener | DefiLlama is not a pair-state feed |
| Supplementary promoted/trending token signal | DexScreener profiles/boosts/metas | Do not relabel it as strict new-pool discovery |
| TVL/yield/stablecoin context | DefiLlama | Do not put this low-frequency context source in the hot discovery loop |

Use `scripts/provider_policy.py` for a deterministic capability guard before introducing a route.

## DexScreener

Base: `https://api.dexscreener.com`. No API key and no researched paid higher-limit tier.

Two independent documented request budgets must not share one limiter:

- **300 requests/minute:** pair/token/search endpoints such as `/latest/dex/pairs/{chainId}/{pairId}`, `/latest/dex/search`, `/token-pairs/v1/{chainId}/{tokenAddress}`, `/tokens/v1/{chainId}/{tokenAddresses}`.
- **60 requests/minute:** profiles/boosts/metas such as `/token-profiles/latest/v1`, `/token-profiles/recent-updates/v1`, `/token-boosts/latest/v1`, `/token-boosts/top/v1`, `/metas/trending/v1`.

There is **no OHLCV/candle endpoint** in the researched REST API. On 429, reduce request pressure and apply bounded backoff; do not retry harder in search of a nonexistent higher public quota.

## GeckoTerminal

Native free base: `https://api.geckoterminal.com/api/v2`, researched at **30 calls/minute**. The similar CoinGecko shared keyless path has a lower researched budget (~10/min), so budget by the actual configured base URL rather than provider name alone.

Relevant routes:

- new pools: `/networks/{network}/new_pools` or `/networks/new_pools`;
- trending pools: `/networks/trending_pools` or `/networks/{network}/trending_pools`;
- OHLCV: `/networks/{network}/pools/{pool_address}/ohlcv/{timeframe}`.

Free-tier constraints in the supplied research: maximum **1,000 candles/request** (100 default), roughly **6 months** historical OHLCV, pools paginated **20/page** with free access capped at **10 pages**, and roughly 10–20 second data refresh. Do not convert any of those limits into guarantees without current official verification.

## DefiLlama

Keyless free APIs include `api.llama.fi`, `coins.llama.fi`, `stablecoins.llama.fi`, and `yields.llama.fi`. It has no dedicated new-token feed. Treat TVL/yield data as contextual enrichment rather than real-time discovery.

The supplied research does **not** establish one reliable free per-endpoint rate limit: official material gives a broad range while third-party estimates differ. Therefore:

- configure a conservative budget;
- monitor 429s;
- honor server hints;
- do not hardcode a third-party estimate as provider policy.

The researched API upgrade is the developer API tier, not the cheaper dashboard-only subscription.

## Failure-sensitive rules

- A DexScreener candle implementation is a routing error, not an HTTP-debugging problem.
- A GeckoTerminal budget is invalid until the configured base URL is known.
- A DefiLlama 429 is not evidence that a specific undocumented numeric limit has been exceeded; treat the free service as fair-use unless current official docs establish more.
- When provider output disagrees, preserve provider identity and timestamps; do not average or overwrite conflicting facts silently.
