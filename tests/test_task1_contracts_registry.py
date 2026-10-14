
import pytest
from pydantic import ValidationError

from src.contracts import AccessMode
from src.registry import build_registry
from src.schemas import OrderLookupInput, RefundRequestInput


def test_registry_contains_expected_tools():
    registry = build_registry()

    lookup = registry.get("order_lookup", "1.0")
    refund = registry.get("refund_request", "1.0")

    assert lookup is not None
    assert lookup.access_mode == AccessMode.READ
    assert lookup.roles == frozenset({"viewer", "operator", "admin"})

    assert refund is not None
    assert refund.access_mode == AccessMode.WRITE
    assert refund.roles == frozenset({"operator", "admin"})


def test_registry_rejects_unknown_tool_or_version():
    registry = build_registry()

    assert registry.get("unknown_tool", "1.0") is None
    assert registry.get("order_lookup", "9.9") is None


def test_valid_order_lookup_input():
    parsed = OrderLookupInput.model_validate(
        {"order_id": "ORD-1001"}
    )

    assert parsed.order_id == "ORD-1001"


def test_invalid_order_lookup_input_is_rejected():
    with pytest.raises(ValidationError):
        OrderLookupInput.model_validate(
            {"order_id": "ORD 1001"}
        )


def test_unknown_order_lookup_field_is_rejected():
    with pytest.raises(ValidationError):
        OrderLookupInput.model_validate(
            {
                "order_id": "ORD-1001",
                "admin": True,
            }
        )


def test_valid_refund_request_input():
    parsed = RefundRequestInput.model_validate(
        {
            "order_id": "ORD-1001",
            "amount": 250.0,
            "reason": "Item arrived damaged",
        }
    )

    assert parsed.amount == 250.0
    assert parsed.approval_id is None


def test_invalid_refund_amount_is_rejected():
    with pytest.raises(ValidationError):
        RefundRequestInput.model_validate(
            {
                "order_id": "ORD-1001",
                "amount": -10,
                "reason": "Refund requested",
            }
        )


def test_invalid_refund_reason_is_rejected():
    with pytest.raises(ValidationError):
        RefundRequestInput.model_validate(
            {
                "order_id": "ORD-1001",
                "amount": 10,
                "reason": "No",
            }
        )
