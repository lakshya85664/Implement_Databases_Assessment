
from __future__ import annotations

from src.contracts import AccessMode, ToolSpec
from src.schemas import (
    OrderLookupInput,
    OrderLookupOutput,
    RefundRequestInput,
    RefundRequestOutput,
)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[tuple[str, str], ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        key = (spec.name, spec.version)

        if key in self._tools:
            raise ValueError(
                f"Tool already registered: {spec.name} v{spec.version}"
            )

        self._tools[key] = spec

    def get(self, name: str, version: str) -> ToolSpec | None:
        return self._tools.get((name, version))

    def list_tools(self) -> list[dict[str, str]]:
        return [
            {
                "name": spec.name,
                "version": spec.version,
                "access_mode": spec.access_mode.value,
                "description": spec.description,
            }
            for spec in sorted(
                self._tools.values(),
                key=lambda item: (item.name, item.version),
            )
        ]


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(
        ToolSpec(
            name="order_lookup",
            version="1.0",
            access_mode=AccessMode.READ,
            roles=frozenset({"viewer", "operator", "admin"}),
            input_model=OrderLookupInput,
            output_model=OrderLookupOutput,
            description="Look up an order by ID.",
        )
    )

    registry.register(
        ToolSpec(
            name="refund_request",
            version="1.0",
            access_mode=AccessMode.WRITE,
            roles=frozenset({"operator", "admin"}),
            input_model=RefundRequestInput,
            output_model=RefundRequestOutput,
            description=(
                "Submit a refund request for approval; "
                "does not authorize payment automatically."
            ),
        )
    )

    return registry
