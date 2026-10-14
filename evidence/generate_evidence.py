
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = ROOT / "evidence"
TRACES_DIR = ROOT / "traces"

sys.path.insert(0, str(ROOT))

from src.database import Database
from src.observability import emit_event
from src.repositories import (
    OrderNotFoundError,
    OrderRepository,
    RefundApprovalError,
    RefundRepository,
)


def write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def record_trace(
    request_id: str,
    tool_name: str,
    status: str,
    *,
    arguments: dict[str, Any],
    result: dict[str, Any] | None = None,
    error_type: str | None = None,
    duration_ms: float = 0.0,
) -> dict[str, Any]:
    event = {
        "request_id": request_id,
        "tool_name": tool_name,
        "status": status,
        "arguments": arguments,
        "result": result,
        "error_type": error_type,
        "duration_ms": round(duration_ms, 3),
    }
    write_json(TRACES_DIR / f"{request_id.lower()}.json", event)
    emit_event(
        "tool_execution",
        request_id=request_id,
        tool_name=tool_name,
        status=status,
        duration_ms=duration_ms,
        error_type=error_type,
    )
    return event


def main() -> int:
    EVIDENCE_DIR.mkdir(exist_ok=True)
    TRACES_DIR.mkdir(exist_ok=True)

    for old_trace in TRACES_DIR.glob("*.json"):
        old_trace.unlink()

    trace_results: list[dict[str, Any]] = []
    durations: list[float] = []

    db = Database(":memory:")
    orders = OrderRepository(db)
    refunds = RefundRepository(db)

    try:
        # Scenario 1: successful order lookup.
        started = time.perf_counter()
        order = orders.lookup("ORD-1001")
        duration = (time.perf_counter() - started) * 1000
        durations.append(duration)
        trace_results.append(
            record_trace(
                "REQ-001",
                "order_lookup",
                "ok",
                arguments={"order_id": "ORD-1001"},
                result=order,
                duration_ms=duration,
            )
        )

        # Scenario 2: refund request awaiting approval.
        started = time.perf_counter()
        refund = refunds.request_refund(
            "ORD-1001",
            100.0,
            "Item arrived damaged",
        )
        duration = (time.perf_counter() - started) * 1000
        durations.append(duration)
        trace_results.append(
            record_trace(
                "REQ-002",
                "refund_request",
                "pending_approval",
                arguments={
                    "order_id": "ORD-1001",
                    "amount": 100.0,
                    "reason": "Item arrived damaged",
                },
                result=refund,
                duration_ms=duration,
            )
        )

        # Scenario 3: refund approved with an explicit approval ID.
        started = time.perf_counter()
        approved = refunds.approve_refund(
            refund["refund_id"],
            "APPROVAL-DEMO-001",
        )
        duration = (time.perf_counter() - started) * 1000
        durations.append(duration)
        trace_results.append(
            record_trace(
                "REQ-003",
                "refund_approval",
                "ok",
                arguments={
                    "refund_id": refund["refund_id"],
                    "approval_id": "APPROVAL-DEMO-001",
                },
                result=approved,
                duration_ms=duration,
            )
        )

        # Scenario 4: missing order.
        started = time.perf_counter()
        try:
            orders.lookup("ORD-MISSING")
        except OrderNotFoundError as exc:
            duration = (time.perf_counter() - started) * 1000
            durations.append(duration)
            trace_results.append(
                record_trace(
                    "REQ-004",
                    "order_lookup",
                    "not_found",
                    arguments={"order_id": "ORD-MISSING"},
                    error_type=type(exc).__name__,
                    duration_ms=duration,
                )
            )

        # Scenario 5: repeated approval rejected.
        started = time.perf_counter()
        try:
            refunds.approve_refund(
                refund["refund_id"],
                "APPROVAL-DEMO-002",
            )
        except RefundApprovalError as exc:
            duration = (time.perf_counter() - started) * 1000
            durations.append(duration)
            trace_results.append(
                record_trace(
                    "REQ-005",
                    "refund_approval",
                    "denied",
                    arguments={
                        "refund_id": refund["refund_id"],
                        "approval_id": "APPROVAL-DEMO-002",
                    },
                    error_type=type(exc).__name__,
                    duration_ms=duration,
                )
            )

        statuses: dict[str, int] = {}
        for item in trace_results:
            status = item["status"]
            statuses[status] = statuses.get(status, 0) + 1

        metrics = {
            "trace_count": len(trace_results),
            "success_count": sum(
                item["status"] == "ok" for item in trace_results
            ),
            "failure_or_rejection_count": sum(
                item["status"] in {"not_found", "denied"}
                for item in trace_results
            ),
            "pending_approval_count": sum(
                item["status"] == "pending_approval"
                for item in trace_results
            ),
            "status_counts": statuses,
            "average_duration_ms": round(
                sum(durations) / len(durations), 3
            ) if durations else 0.0,
            "max_duration_ms": round(max(durations), 3)
            if durations else 0.0,
            "note": (
                "Durations are local demonstration measurements, "
                "not production benchmarks."
            ),
        }

        write_json(EVIDENCE_DIR / "metrics_summary.json", metrics)

    finally:
        db.close()

    # Record the actual test command result instead of assuming success.
    test_run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    test_evidence = {
        "command": "python -m pytest -q",
        "return_code": test_run.returncode,
        "stdout": test_run.stdout,
        "stderr": test_run.stderr,
        "passed": test_run.returncode == 0,
    }
    write_json(EVIDENCE_DIR / "test_results.json", test_evidence)

    architecture = """flowchart TD
    A[Agent / Caller] --> B[Tool Contracts and Registry]
    B --> C[Pydantic Input Validation]
    C --> D[Repositories]
    D --> E[SQLite Database]
    E --> F[Orders Table]
    E --> G[Refunds Table]
    D --> H[Approval Gate]
    B --> I[Structured Observability]
    I --> J[JSON Traces and Metrics]
    """

    (EVIDENCE_DIR / "architecture.mmd").write_text(
        architecture,
        encoding="utf-8",
    )

    print("Task 5 — Evidence Generation")
    print("=" * 40)
    print(f"Traces created: {len(list(TRACES_DIR.glob('*.json')))}")
    print("Created: evidence/metrics_summary.json")
    print("Created: evidence/test_results.json")
    print("Created: evidence/architecture.mmd")
    print()
    print(test_run.stdout.strip())

    if test_run.returncode != 0:
        print(test_run.stderr)
        return test_run.returncode

    print("\nEvidence generation completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
