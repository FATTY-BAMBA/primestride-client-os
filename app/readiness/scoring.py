"""Deterministic readiness scoring and gap intelligence.

This is the stable home for the evidence-coverage / readiness-range model that
previously lived in ``v082_perf.py``. Unknown evidence stays unknown, and gap
ranking is derived only from the reviewed rubric state.
"""
from __future__ import annotations

DOMAIN_VERSION = "1.3.3"

GAP_REQUEST_COPY = {
    (4, "pricing_rules"): (
        "Pricing rules / exception logic",
        "Closes the remaining quoting logic gap without asking for more quote history.",
    ),
    (5, "order_reference"): (
        "Order / customer reference",
        "Confirms how accepted quotes, orders and work orders connect.",
    ),
    (6, "kpi_definitions"): (
        "Existing management report or KPI definition",
        "Shows which management numbers are considered authoritative.",
    ),
    (6, "revenue"): (
        "Trusted revenue field or report",
        "Needed before revenue analysis can be treated as operational truth.",
    ),
    (6, "margin"): (
        "Margin / gross-profit definition",
        "Confirms how management defines profitability before AI interprets it.",
    ),
    (6, "order_history"): (
        "Order history / order-level dataset",
        "Fills the operational link between quote history and work-order history.",
    ),
}


def honest_summary(summary: dict) -> dict:
    """Return evidence coverage plus honest minimum/maximum readiness."""
    required_total = 0.0
    reviewed_weight = 0.0
    earned_weight = 0.0
    awaiting_weight = 0.0

    available_items = []
    partial_items = []
    missing_items = []
    awaiting_items = []

    for criterion in summary["criteria"]:
        status = criterion["status"]
        weight = float(criterion["weight"])
        if status == "not_required":
            continue
        required_total += weight
        if status == "available":
            reviewed_weight += weight
            earned_weight += weight
            available_items.append(criterion)
        elif status == "partial":
            reviewed_weight += weight
            earned_weight += weight * 0.5
            partial_items.append(criterion)
        elif status == "missing":
            reviewed_weight += weight
            missing_items.append(criterion)
        else:
            awaiting_weight += weight
            awaiting_items.append(criterion)

    coverage = (reviewed_weight / required_total * 100.0) if required_total else 100.0
    minimum = (earned_weight / required_total * 100.0) if required_total else 100.0
    maximum = (
        (earned_weight + awaiting_weight) / required_total * 100.0
        if required_total else 100.0
    )
    final = not awaiting_items

    out = dict(summary)
    out.update({
        "coverage": coverage,
        "range_min": minimum,
        "range_max": maximum,
        "final": final,
        "display_score": minimum if final else None,
        "available_items": available_items,
        "partial_items": partial_items,
        "missing_items": missing_items,
        "awaiting_items": awaiting_items,
        "confirmed_weight": earned_weight,
        "unknown_weight": awaiting_weight,
    })
    return out


def honest_summaries(main_module, company) -> list[dict]:
    return [honest_summary(summary) for summary in main_module.readiness_summaries(company)]


def gap_intelligence(summaries: list[dict]) -> dict:
    """Build the smallest evidence-based next-gap brief."""
    gaps = []
    do_not_ask = []
    known_by_module = []

    for summary in summaries:
        available = summary["available_items"]
        partial = summary["partial_items"]
        missing = summary["missing_items"]
        awaiting = summary["awaiting_items"]

        known_by_module.append({
            "module_no": summary["module_no"],
            "name": summary["name"],
            "coverage": summary["coverage"],
            "available": available[:5],
            "partial": partial,
            "missing": missing,
            "awaiting_count": len(awaiting),
        })

        for criterion in available:
            do_not_ask.append({
                "module_no": summary["module_no"],
                "label": criterion["label"],
                "source": criterion.get("source"),
            })

        for criterion in awaiting:
            module_no = summary["module_no"]
            key = criterion["key"]
            title, reason = GAP_REQUEST_COPY.get(
                (module_no, key),
                (criterion["label"], f"This criterion is still unevidenced for Module {module_no:02d}."),
            )
            business_boost = 8 if (module_no, key) == (6, "kpi_definitions") else 0
            priority = summary["coverage"] * 10 + float(criterion["weight"]) + business_boost
            gaps.append({
                "module_no": module_no,
                "key": key,
                "title": title,
                "reason": reason,
                "weight": criterion["weight"],
                "priority": priority,
            })

    gaps.sort(key=lambda item: (-item["priority"], item["module_no"], item["title"]))

    deduped = []
    seen = set()
    for item in do_not_ask:
        key = item["label"].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    return {
        "known_by_module": known_by_module,
        "ask_next": gaps[:3],
        "remaining_gaps": gaps[3:],
        "do_not_ask": deduped[:12],
    }


# Compatibility names used by historical modules.
_honest_summary = honest_summary
_honest_summaries = honest_summaries
_gap_intelligence = gap_intelligence

__all__ = [
    "DOMAIN_VERSION",
    "GAP_REQUEST_COPY",
    "honest_summary",
    "honest_summaries",
    "gap_intelligence",
    "_honest_summary",
    "_honest_summaries",
    "_gap_intelligence",
]
