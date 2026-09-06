from app.readiness.scoring import gap_intelligence, honest_summary


def test_unknown_evidence_stays_unknown_in_readiness_range():
    summary = {
        "module_no": 4,
        "name": "AI Quoting",
        "criteria": [
            {"key": "historical_quotes", "label": "Historical quotations", "weight": 50, "status": "available", "source": "quotes.xlsx"},
            {"key": "pricing_rules", "label": "Pricing rules", "weight": 50, "status": "awaiting", "source": None},
        ],
    }
    result = honest_summary(summary)
    assert result["coverage"] == 50
    assert result["range_min"] == 50
    assert result["range_max"] == 100
    assert result["confirmed_weight"] == 50
    assert result["unknown_weight"] == 50
    assert result["final"] is False
    assert result["display_score"] is None

    gaps = gap_intelligence([result])
    assert gaps["ask_next"][0]["key"] == "pricing_rules"
    assert any(item["label"] == "Historical quotations" for item in gaps["do_not_ask"])
