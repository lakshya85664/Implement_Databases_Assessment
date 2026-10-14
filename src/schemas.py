
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr


class StrictInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class OrderLookupInput(StrictInput):
    order_id: StrictStr = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="Unique order identifier",
    )


class OrderLookupOutput(BaseModel):
    order_id: str
    status: str
    total_amount: float = Field(ge=0)


class RefundRequestInput(StrictInput):
    order_id: StrictStr = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    amount: float = Field(gt=0, le=1_000_000)
    reason: StrictStr = Field(min_length=5, max_length=300)
    approval_id: StrictStr | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )


class RefundRequestOutput(BaseModel):
    refund_id: str
    order_id: str
    amount: float
    status: Literal["pending_approval", "approved", "rejected"]
    approval_required: bool
