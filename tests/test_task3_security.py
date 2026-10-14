
import sqlite3

import pytest
from pydantic import ValidationError

from src.database import Database
from src.repositories import (
    OrderNotFoundError,
    OrderRepository,
    RefundApprovalError,
    RefundRepository,
)
from src.schemas import OrderLookupInput, RefundRequestInput


@pytest.fixture
def database():
    db = Database(":memory:")
    yield db
    db.close()


def test_order_id_rejects_sql_injection_input():
    with pytest.raises(ValidationError):
        OrderLookupInput(order_id="' OR 1=1 --")


def test_order_lookup_does_not_expose_other_orders(database):
    repository = OrderRepository(database)

    with pytest.raises(OrderNotFoundError):
        repository.lookup("' OR 1=1 --")


def test_refund_schema_rejects_unexpected_fields():
    with pytest.raises(ValidationError):
        RefundRequestInput(
            order_id="ORD-1001",
            amount=100.0,
            reason="Item arrived damaged",
            bypass_approval=True,
        )


@pytest.mark.parametrize("amount", [0, -1, 1_000_001])
def test_refund_schema_rejects_invalid_amounts(amount):
    with pytest.raises(ValidationError):
        RefundRequestInput(
            order_id="ORD-1001",
            amount=amount,
            reason="Item arrived damaged",
        )


def test_refund_request_rejects_missing_order(database):
    repository = RefundRepository(database)

    with pytest.raises(OrderNotFoundError):
        repository.request_refund(
            "ORD-9999", 100.0, "Item arrived damaged"
        )


def test_refund_request_does_not_accept_approval_shortcut(database):
    repository = RefundRepository(database)

    refund = repository.request_refund(
        "ORD-1001",
        100.0,
        "Item arrived damaged",
        approval_id="UNTRUSTED-APPROVAL",
    )

    stored = repository.get_refund(refund["refund_id"])

    assert stored is not None
    assert stored["status"] == "pending_approval"
    assert stored["approval_id"] is None


def test_refund_cannot_be_approved_twice(database):
    repository = RefundRepository(database)

    refund = repository.request_refund(
        "ORD-1001", 100.0, "Item arrived damaged"
    )

    repository.approve_refund(refund["refund_id"], "APPROVAL-001")

    with pytest.raises(RefundApprovalError):
        repository.approve_refund(refund["refund_id"], "APPROVAL-002")


def test_missing_refund_cannot_be_approved(database):
    repository = RefundRepository(database)

    with pytest.raises(OrderNotFoundError):
        repository.approve_refund("REF-DOES-NOT-EXIST", "APPROVAL-001")


def test_database_enforces_refund_foreign_key(database):
    with pytest.raises(sqlite3.IntegrityError):
        with database.transaction():
            database.execute(
                """
                INSERT INTO refunds (
                    refund_id, order_id, amount, reason, status
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "REF-INVALID",
                    "ORD-DOES-NOT-EXIST",
                    10.0,
                    "Invalid order test",
                    "pending_approval",
                ),
            )


def test_database_rejects_invalid_refund_status(database):
    with pytest.raises(sqlite3.IntegrityError):
        with database.transaction():
            database.execute(
                """
                INSERT INTO refunds (
                    refund_id, order_id, amount, reason, status
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "REF-BAD-STATUS",
                    "ORD-1001",
                    10.0,
                    "Invalid status test",
                    "paid_without_approval",
                ),
            )
