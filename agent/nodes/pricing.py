"""Pricing Strategist: market statistics + client budget + the user's floor -> a price, and whether
the Connects cost is worth it. Computed, not generated: an injected "bid $5" can't move it."""

from __future__ import annotations

from agent.handoffs import PriceQuote
from agent.nodes.common import Ctx, node

CATEGORIES = {"development", "data_science", "marketing", "3d_design"}
USD_PER_CONNECT = 0.15          # Upwork sells Connects at about this price
EST_HOURS = 20                  # hourly jobs: rough job size for the expected-value check


def quote(job: dict, stats: dict, user: dict, balance: int, fit_score: float, reserve: int) -> PriceQuote:
    hourly = job.get("payment_type") == "hourly"
    market = stats["hourly_rate"] if hourly else stats["fixed_total_paid"]
    low, high = market["p25"], market["p75"]
    bmin, bmax = job.get("budget_min"), job.get("budget_max")
    floor = user["hourly_floor"] if hourly else user["fixed_floor"]
    if hourly:
        target = user.get("hourly_rate") or market["p50"]
        if bmax is not None:
            target = min(max(target, bmin or bmax), bmax)
            low, high = max(min(low, bmax), bmin or 0), bmax
    else:
        target = 0.95 * bmax if bmax is not None else market["p50"]
        if bmax is not None:
            low, high = 0.8 * bmax, bmax
    amount = round(max(target, floor), 2)
    cost = int(job.get("connects_cost") or 0)
    expected = 0.3 * fit_score * (amount * (EST_HOURS if hourly else 1))   # rough: reply x win chance x value
    worth = balance - cost >= reserve and expected > cost * USD_PER_CONNECT
    unit = "usd_per_hour" if hourly else "usd_total"
    why = (f"{'Client range' if bmax else 'Market median'} with market p25-p75 {market['p25']:.0f}-{market['p75']:.0f}"
           f"{'/hr' if hourly else ''}; your floor {floor}. {cost} Connects of {balance}"
           f"{' (keeps the reserve)' if balance - cost >= reserve else ' (would breach the reserve)'}.")
    return PriceQuote(amount=amount, unit=unit, band_low=round(low, 2), band_high=round(max(high, low), 2),
                      connects_cost=cost, worth_connects=worth, rationale=why)


@node("pricing")
async def pricing(state: dict, ctx: Ctx) -> dict:
    job = state["job"]
    cat = job.get("category") if job.get("category") in CATEGORIES else None
    stats = await ctx.tool("pricing", "marketplace", "get_market_stats", {"category": cat} if cat else {})
    bal = (await ctx.tool("pricing", "marketplace", "get_connects_balance", {}))["balance"]
    q = quote(job, stats, state["user"], bal, state["fit_report"]["score"], ctx.deps.cfg["thresholds"]["min_connects_reserve"])
    update = {"price_quote": q.model_dump(), "_summary": f"{q.amount} {q.unit}, worth Connects: {q.worth_connects}"}
    if not q.worth_connects:
        update.update(status="skipped", status_reason=f"not worth the Connects: {q.rationale}")
    return update
