
import pytest

from src.database import Database
from src.repositories import (
    OrderNotFoundError,
    OrderRepository,
    RefundApprovalError,
    RefundRepository,
)


@pytest.fixture
def database():
    db = Database(":memory:")
    yield db
    db.close()


def test_order_lookup_returns_seeded_order(database):
    repository = OrderRepository(database)

    order = repository.lookup("ORD-1001")

    assert order["order_id"] == "ORD-1001"
    assert order["status"] == "shipped"
    assert order["total_amount"] == 1250.00


def test_order_lookup_missing_order_raises(database):
    repository = OrderRepository(database)

    with pytest.raises(OrderNotFoundError):
        repository.lookup("ORD-9999")


def test_lookup_uses_parameterized_query(database):
    repository = OrderRepository(database)

    with pytest.raises(OrderNotFoundError):
        repository.lookup("' OR 1=1 --")


def test_refund_request_starts_pending(database):
    repository = RefundRepository(database)

    refund = repository.request_refund(
        "ORD-1001",
        250.0,
        "Item arrived damaged",
    )

    assert refund["status"] == "pending_approval"
    assert refund["approval_required"] is True

    stored = repository.get_refund(refund["refund_id"])
    assert stored is not None
    assert stored["status"] == "pending_approval"
    assert stored["approval_id"] is None


def test_refund_cannot_exceed_order_total(database):
    repository = RefundRepository(database)

    with pytest.raises(ValueError):
        repository.request_refund(
            "ORD-1001",
            2000.0,
            "Item arrived damaged",
        )


def test_refund_for_missing_order_is_rejected(database):
    repository = RefundRepository(database)

    with pytest.raises(OrderNotFoundError):
        repository.request_refund(
            "ORD-9999",
            10.0,
            "Item arrived damaged",
        )


def test_approval_requires_approval_id(database):
    repository = RefundRepository(database)
    refund = repository.request_refund(
        "ORD-1001",
        100.0,
        "Item arrived damaged",
    )

    with pytest.raises(RefundApprovalError):
        repository.approve_refund(
            refund["refund_id"],
            " ",
        )


def test_approved_refund_records_approval_id(database):
    repository = RefundRepository(database)
    refund = repository.request_refund(
        "ORD-1001",
        100.0,
        "Item arrived damaged",
    )

    approved = repository.approve_refund(
        refund["refund_id"],
        "APPROVAL-001",
    )

    assert approved["status"] == "approved"
    assert approved["approval_id"] == "APPROVAL-001"
