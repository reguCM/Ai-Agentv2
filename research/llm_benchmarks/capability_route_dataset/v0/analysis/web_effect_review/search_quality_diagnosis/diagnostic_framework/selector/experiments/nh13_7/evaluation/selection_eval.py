"""Stage 1 selection evaluation vs human gold relevant terms."""

from __future__ import annotations

from typing import Any


def selection_metrics(
    predicted: list[str],
    gold: list[str],
) -> dict[str, Any]:
    pred = set(predicted)
    g = set(gold)
    inter = pred & g
    precision = len(inter) / len(pred) if pred else 0.0
    recall = len(inter) / len(g) if g else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "gold_terms": sorted(g),
        "predicted_terms": sorted(pred),
        "missed_terms": sorted(g - pred),
        "unnecessary_terms": sorted(pred - g),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "gold_count": len(g),
        "predicted_count": len(pred),
    }


def aggregate_selection(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    n = len(rows)
    return {
        "cases": n,
        "mean_precision": round(sum(r["precision"] for r in rows) / n, 4),
        "mean_recall": round(sum(r["recall"] for r in rows) / n, 4),
        "mean_f1": round(sum(r["f1"] for r in rows) / n, 4),
        "mean_predicted_count": round(sum(r["predicted_count"] for r in rows) / n, 2),
        "mean_gold_count": round(sum(r["gold_count"] for r in rows) / n, 2),
        "total_missed": sum(len(r["missed_terms"]) for r in rows),
        "total_unnecessary": sum(len(r["unnecessary_terms"]) for r in rows),
    }
