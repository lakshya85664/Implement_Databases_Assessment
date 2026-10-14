
import json
import logging
import sqlite3

from src.database import Database
from src.observability import (
    OperationTimer,
    configure_logging,
    emit_event,
)
from src.repositories import RefundRepository


def test_structured_event_contains_required_fields(caplog):
    configure_logging()

    with caplog.at_level(logging.INFO, logger="database_tools"):
        event = emit_event(
            "database_operation",
            request_id="REQ-001",
            tool_name="order_lookup",
            status="ok",
            duration_ms=12.34567,
        )

    assert event["event"] == "database_operation"
    assert event["request_id"] == "REQ-001"
    assert event["tool_name"] == "order_lookup"
    assert event["status"] == "ok"
    assert event["duration_ms"] == 12.346

    logged_event = json.loads(caplog.records[-1].message)
    assert logged_event["request_id"] == "REQ-001"


def test_structured_event_records_error_type(caplog):
    configure_logging()

    with caplog.at_level(logging.INFO, logger="database_tools"):
        event = emit_event(
            "database_operation",
            request_id="REQ-002",
            tool_name="refund_request",
            status="failed",
            error_type="IntegrityError",
        )

    assert event["status"] == "failed"
    assert event["error_type"] == "IntegrityError"


def test_structured_event_does_not_include_raw_arguments(caplog):
    configure_logging()

    with caplog.at_level(logging.INFO, logger="database_tools"):
        emit_event(
            "database_operation",
            request_id="REQ-003",
            tool_name="refund_request",
            status="ok",
        )

    message = caplog.records[-1].message
    assert "approval_id" not in message
    assert "password" not in message


def test_operation_timer_records_nonnegative_duration():
    with OperationTimer() as timer:
        sum(range(1000))

    assert timer.duration_ms >= 0


def test_failed_refund_transaction_rolls_back(database_path=None):
    db = Database(":memory:")

    try:
        repository = RefundRepository(db)

        try:
            with db.transaction():
                repository.request_refund(
                    "ORD-1001",
                    100.0,
                    "Item arrived damaged",
                )
                raise RuntimeError("Simulated transaction failure")
        except RuntimeError:
            pass

        refunds = db.fetch_all("SELECT * FROM refunds", ())
        assert refunds == []
    finally:
        db.close()


def test_database_rejects_duplicate_refund_id():
    db = Database(":memory:")

    try:
        with db.transaction():
            db.execute(
                """
                INSERT INTO refunds (
                    refund_id, order_id, amount, reason, status
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "REF-DUPLICATE",
                    "ORD-1001",
                    10.0,
                    "First refund",
                    "pending_approval",
                ),
            )

        try:
            with db.transaction():
                db.execute(
                    """
                    INSERT INTO refunds (
                        refund_id, order_id, amount, reason, status
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "REF-DUPLICATE",
                        "ORD-1001",
                        20.0,
                        "Duplicate refund",
                        "pending_approval",
                    ),
                )
        except sqlite3.IntegrityError:
            pass

        refunds = db.fetch_all(
            "SELECT * FROM refunds WHERE refund_id = ?",
            ("REF-DUPLICATE",),
        )

        assert len(refunds) == 1
        assert refunds[0]["amount"] == 10.0
    finally:
        db.close()
