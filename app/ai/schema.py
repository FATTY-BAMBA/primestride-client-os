"""Stable schemas and controlled vocabularies for multimodal intake."""
from __future__ import annotations

from typing import Any

CATEGORY_VALUES = ["customers", "products", "quotes", "work_orders", "reports", "other"]
READINESS_KEYS = {
    4: ["historical_quotes", "customer_identity", "product_spec", "quantity", "quoted_price", "accepted_price", "material_cost", "processing_cost", "pricing_rules", "exception_examples"],
    5: ["work_order_id", "order_reference", "product_spec", "quantity", "promised_date", "production_stages", "station_machine", "assignee", "current_status", "actual_timestamps", "exceptions"],
    6: ["quote_history", "order_history", "work_order_history", "revenue", "cost", "margin", "customer_product", "time_fields", "production_events", "kpi_definitions"],
}

# Historical v0.9 canonical list retained for compatibility imports.
CANONICAL_TARGETS = [
    "Customer.code", "Customer.name", "Contact.name",
    "Product.code", "Product.name", "Specification.value", "Material.name",
    "Quote.quote_number", "Quote.created_at", "Quote.status", "Quote.salesperson",
    "QuoteLine.quantity", "QuoteLine.unit_price", "Quote.total", "Quote.accepted_price",
    "MaterialCost.unit_cost", "Cost.processing", "PricingRule.note", "Quote.exception_note",
    "Order.order_number", "OrderLine.quantity",
    "WorkOrder.work_order_number", "WorkOrder.promised_date", "WorkOrder.status",
    "WorkOrderLine.quantity", "Operation.stage", "Operation.machine", "Operation.assignee",
    "Operation.actual_start", "Operation.actual_end", "WorkException.reason",
    "Metric.revenue", "Metric.cost", "Metric.margin", "MetricDefinition.name",
]

CANONICAL_TARGETS_092 = [
    "Customer.code", "Customer.name", "Contact.name",
    "Product.code", "Product.name", "Specification.value", "Material.name",
    "Quote.quote_number", "Quote.created_at", "Quote.status", "Quote.salesperson",
    "QuoteLine.quantity", "QuoteLine.unit_price", "Quote.total", "Quote.accepted_price",
    "MaterialCost.unit_cost", "Cost.processing", "PricingRule.note", "Quote.exception_note",
    "Order.order_number", "OrderLine.quantity",
    "WorkOrder.work_order_number", "WorkOrder.created_at", "WorkOrder.promised_date",
    "WorkOrder.status", "WorkOrder.salesperson", "WorkOrderLine.quantity",
    "Operation.stage", "Operation.machine", "Operation.assignee",
    "Operation.planned_start", "Operation.planned_end",
    "Operation.actual_start", "Operation.actual_end", "Operation.note",
    "WorkInstruction.text", "WorkConstraint.text", "WorkException.reason",
    "Metric.revenue", "Metric.cost", "Metric.margin", "MetricDefinition.name",
]

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "category": {"type": "string", "enum": CATEGORY_VALUES},
        "document_type": {"type": "string"},
        "summary": {"type": "string"},
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "source_label": {"type": "string"},
                    "canonical_target": {"type": "string"},
                    "value": {"type": "string"},
                    "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                    "evidence": {"type": "string"},
                },
                "required": ["source_label", "canonical_target", "value", "confidence", "evidence"],
            },
        },
        "readiness": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "module_no": {"type": "integer", "enum": [4, 5, 6]},
                    "criterion": {"type": "string"},
                    "status": {"type": "string", "enum": ["available", "partial"]},
                    "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                    "reason": {"type": "string"},
                },
                "required": ["module_no", "criterion", "status", "confidence", "reason"],
            },
        },
        "quality_flags": {"type": "array", "items": {"type": "string"}},
        "questions": {"type": "array", "items": {"type": "string"}},
        "do_not_infer": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["category", "document_type", "summary", "fields", "readiness", "quality_flags", "questions", "do_not_infer"],
}

OUTPUT_SCHEMA_092: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "category": {"type": "string", "enum": CATEGORY_VALUES},
        "document_type": {"type": "string"},
        "summary": {"type": "string"},
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "source_section": {"type": "string"},
                    "source_label": {"type": "string"},
                    "canonical_target": {"type": "string"},
                    "value": {"type": "string"},
                    "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                    "evidence": {"type": "string"},
                    "semantic_role": {
                        "type": "string",
                        "enum": ["identity", "date", "quantity", "status", "specification", "schedule", "instruction", "constraint", "exception", "note", "other"],
                    },
                },
                "required": ["source_section", "source_label", "canonical_target", "value", "confidence", "evidence", "semantic_role"],
            },
        },
        "operations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "stage": {"type": "string"},
                    "planned_start": {"type": "string"},
                    "planned_end": {"type": "string"},
                    "actual_start": {"type": "string"},
                    "actual_end": {"type": "string"},
                    "assignee": {"type": "string"},
                    "machine": {"type": "string"},
                    "note": {"type": "string"},
                    "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                    "evidence": {"type": "string"},
                },
                "required": ["stage", "planned_start", "planned_end", "actual_start", "actual_end", "assignee", "machine", "note", "confidence", "evidence"],
            },
        },
        "instructions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "kind": {"type": "string", "enum": ["instruction", "constraint", "exception", "incident", "note"]},
                    "text": {"type": "string"},
                    "canonical_target": {"type": "string"},
                    "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                    "evidence": {"type": "string"},
                },
                "required": ["kind", "text", "canonical_target", "confidence", "evidence"],
            },
        },
        "readiness": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "module_no": {"type": "integer", "enum": [4, 5, 6]},
                    "criterion": {"type": "string"},
                    "status": {"type": "string", "enum": ["available", "partial"]},
                    "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                    "reason": {"type": "string"},
                },
                "required": ["module_no", "criterion", "status", "confidence", "reason"],
            },
        },
        "quality_flags": {"type": "array", "items": {"type": "string"}},
        "questions": {"type": "array", "items": {"type": "string"}},
        "do_not_infer": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["category", "document_type", "summary", "fields", "operations", "instructions", "readiness", "quality_flags", "questions", "do_not_infer"],
}
