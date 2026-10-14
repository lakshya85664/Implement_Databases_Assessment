
from __future__ import annotations

import uuid
from typing import Any

from src.database import Database


class OrderNotFoundError(Exception):
    """Raised when an order does not exist."""


class RefundApprovalError(Exception):
    """Raised when a refund action lacks required approval."""


class OrderRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def lookup(self, order_id: str) -> dict[str, Any]:
        """Look up an order using a parameterized query."""
        order = self.database.fetch_one(
            """
            SELECT order_id, status, total_amount
            FROM orders
            WHERE order_id = ?
            """,
            (order_id,),
        )

        if order is None:
            raise OrderNotFoundError(order_id)

        return order


class RefundRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def request_refund(
        self,
        order_id: str,
        amount: float,
        reason: str,
        approval_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a refund request without automatically approving it."""
        order = self.database.fetch_one(
            "SELECT order_id, total_amount FROM orders WHERE order_id = ?",
            (order_id,),
        )

        if order is None:
            raise OrderNotFoundError(order_id)

        if amount > order["total_amount"]:
            raise ValueError("Refund amount exceeds order total")

        refund_id = f"REF-{uuid.uuid4().hex[:12].upper()}"

        # A request remains pending even if an approval ID is supplied.
        # Approval must be performed by a separate authorized operation.
        with self.database.transaction():
            self.database.execute(
                """
                INSERT INTO refunds (
                    refund_id, order_id, amount, reason,
                    status, approval_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    refund_id,
                    order_id,
                    amount,
                    reason,
                    "pending_approval",
                    None,
                ),
            )

        return {
            "refund_id": refund_id,
            "order_id": order_id,
            "amount": amount,
            "status": "pending_approval",
            "approval_required": True,
        }

    def get_refund(self, refund_id: str) -> dict[str, Any] | None:
        return self.database.fetch_one(
            """
            SELECT refund_id, order_id, amount, reason,
                   status, approval_id, created_at
            FROM refunds
            WHERE refund_id = ?
            """,
            (refund_id,),
        )

    def approve_refund(
        self,
        refund_id: str,
        approval_id: str,
    ) -> dict[str, Any]:
        """Approve a pending refund when an approval ID is supplied."""
        if not approval_id.strip():
            raise RefundApprovalError("A valid approval ID is required")

        with self.database.transaction():
            refund = self.database.fetch_one(
                """
                SELECT refund_id, order_id, amount, status
                FROM refunds
                WHERE refund_id = ?
                """,
                (refund_id,),
            )

            if refund is None:
                raise OrderNotFoundError(refund_id)

            if refund["status"] != "pending_approval":
                raise RefundApprovalError(
                    "Only pending refunds can be approved"
                )

            self.database.execute(
                """
                UPDATE refunds
                SET status = ?, approval_id = ?
                WHERE refund_id = ?
                """,
                ("approved", approval_id, refund_id),
            )

        result = self.get_refund(refund_id)
        assert result is not None
        return result
