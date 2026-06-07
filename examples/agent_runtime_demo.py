from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
import json


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Message:
    role: str
    content: str


@dataclass
class ToolCall:
    tool_call_id: str
    name: str
    args: dict[str, Any]


@dataclass
class ToolResult:
    tool_call_id: str
    name: str
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class PolicyDecision:
    required: bool
    reason: str
    approver_hint: str | None = None


@dataclass
class RuntimeEvent:
    seq: int
    event_type: str
    run_id: str
    step: int
    details: dict[str, Any]
    created_at: str


@dataclass
class AgentSpec:
    agent_id: str
    name: str
    instructions: str
    tools: list[str]
    max_turns: int = 8


@dataclass
class ModelAction:
    kind: str
    reason: str
    tool_call: ToolCall | None = None
    final_output: str | None = None


@dataclass
class RunState:
    run_id: str
    agent: AgentSpec
    user_input: str
    status: str
    turn: int = 0
    messages: list[Message] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    scratchpad: dict[str, Any] = field(default_factory=dict)
    pending_tool_call: ToolCall | None = None
    approvals: list[dict[str, Any]] = field(default_factory=list)
    final_output: str | None = None
    events: list[RuntimeEvent] = field(default_factory=list)
    checkpoints: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ToolSpec:
    name: str
    func: Callable[..., dict[str, Any]]
    approval_policy: Callable[[RunState, ToolCall], PolicyDecision] | None = None
    idempotency_key: Callable[[ToolCall], str] | None = None


class ToolGateway:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._idempotency_cache: dict[str, ToolResult] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def dispatch(
        self,
        run: RunState,
        call: ToolCall,
        approved: bool | None = None,
    ) -> tuple[str, PolicyDecision | None, ToolResult | None]:
        if call.name not in self._tools:
            return (
                "executed",
                None,
                ToolResult(
                    tool_call_id=call.tool_call_id,
                    name=call.name,
                    ok=False,
                    error=f"unknown tool: {call.name}",
                ),
            )

        spec = self._tools[call.name]
        decision = spec.approval_policy(run, call) if spec.approval_policy else None

        if decision and decision.required and approved is None:
            return "approval_required", decision, None

        if decision and decision.required and approved is False:
            return (
                "executed",
                decision,
                ToolResult(
                    tool_call_id=call.tool_call_id,
                    name=call.name,
                    ok=False,
                    error="denied_by_human",
                    data={"policy_reason": decision.reason},
                ),
            )

        cache_key = spec.idempotency_key(call) if spec.idempotency_key else None
        if cache_key and cache_key in self._idempotency_cache:
            cached = deepcopy(self._idempotency_cache[cache_key])
            cached.tool_call_id = call.tool_call_id
            return "executed", decision, cached

        try:
            data = spec.func(**call.args)
            result = ToolResult(
                tool_call_id=call.tool_call_id,
                name=call.name,
                ok=True,
                data=data,
            )
            if cache_key:
                self._idempotency_cache[cache_key] = deepcopy(result)
            return "executed", decision, result
        except Exception as exc:  # pragma: no cover - demo keeps error visible.
            return (
                "executed",
                decision,
                ToolResult(
                    tool_call_id=call.tool_call_id,
                    name=call.name,
                    ok=False,
                    error=str(exc),
                ),
            )


class MockRefundModel:
    """Deterministic model stub used to make the runtime example runnable."""

    def next_action(self, run: RunState) -> ModelAction:
        order_id = run.scratchpad.get("order_id") or extract_order_id(run.user_input)
        run.scratchpad["order_id"] = order_id

        if "order" not in run.scratchpad:
            return ModelAction(
                kind="tool_call",
                reason="Need order facts before deciding refund eligibility.",
                tool_call=ToolCall(
                    tool_call_id=f"tool_{run.turn + 1:03d}",
                    name="lookup_order",
                    args={"order_id": order_id},
                ),
            )

        order = run.scratchpad["order"]
        if run.scratchpad.get("refund_denied"):
            return ModelAction(
                kind="final",
                reason="Human reviewer denied the high-risk refund.",
                final_output=(
                    f"Order {order_id} was not refunded because the approval request "
                    "was denied. Escalate to a support lead if the customer disputes it."
                ),
            )

        if order["delivery_status"] == "lost" and "refund" not in run.scratchpad:
            return ModelAction(
                kind="tool_call",
                reason="Lost package is eligible for refund, but refund tool may require approval.",
                tool_call=ToolCall(
                    tool_call_id=f"tool_{run.turn + 1:03d}",
                    name="issue_refund",
                    args={
                        "order_id": order_id,
                        "amount": order["amount"],
                        "reason": "package_lost",
                    },
                ),
            )

        if "refund" in run.scratchpad:
            refund = run.scratchpad["refund"]
            return ModelAction(
                kind="final",
                reason="Refund has been issued successfully.",
                final_output=(
                    f"Refund {refund['refund_id']} was issued for order {order_id} "
                    f"with amount {refund['amount']}."
                ),
            )

        return ModelAction(
            kind="final",
            reason="Order is not eligible for the configured refund policy.",
            final_output=f"Order {order_id} is not eligible for an automatic refund.",
        )


class AgentRuntime:
    def __init__(self, model: MockRefundModel, gateway: ToolGateway) -> None:
        self.model = model
        self.gateway = gateway
        self.runs: dict[str, RunState] = {}
        self._run_seq = 0

    def create_run(self, agent: AgentSpec, user_input: str) -> RunState:
        self._run_seq += 1
        run = RunState(
            run_id=f"run_{self._run_seq:03d}",
            agent=agent,
            user_input=user_input,
            status="created",
            messages=[Message(role="user", content=user_input)],
        )
        self.runs[run.run_id] = run
        self._record_event(run, "run.created", {"agent": agent.name})
        self._checkpoint(run, "created")
        return run

    def run_until_blocked_or_done(self, run_id: str) -> RunState:
        run = self.runs[run_id]
        if run.status in {"created", "queued", "paused"}:
            run.status = "running"
            self._record_event(run, "run.started", {})

        while run.status == "running":
            if run.turn >= run.agent.max_turns:
                run.status = "failed"
                run.final_output = "Stopped because max_turns was reached."
                self._record_event(run, "run.failed", {"reason": "max_turns"})
                self._checkpoint(run, "failed")
                return run

            self._checkpoint(run, f"before_turn_{run.turn + 1}")
            action = self.model.next_action(run)
            run.turn += 1
            self._record_event(
                run,
                "model.action",
                {"kind": action.kind, "reason": action.reason},
            )

            if action.kind == "final":
                run.status = "completed"
                run.final_output = action.final_output
                run.messages.append(Message(role="assistant", content=action.final_output or ""))
                self._record_event(run, "run.completed", {"output": run.final_output})
                self._checkpoint(run, "completed")
                return run

            if action.kind != "tool_call" or action.tool_call is None:
                run.status = "failed"
                run.final_output = f"Unsupported model action: {action.kind}"
                self._record_event(run, "run.failed", {"reason": run.final_output})
                self._checkpoint(run, "failed")
                return run

            mode, decision, result = self.gateway.dispatch(run, action.tool_call)
            self._record_event(
                run,
                "tool.dispatch",
                {
                    "tool": action.tool_call.name,
                    "mode": mode,
                    "args": action.tool_call.args,
                },
            )

            if mode == "approval_required":
                run.status = "awaiting_approval"
                run.pending_tool_call = action.tool_call
                self._record_event(
                    run,
                    "approval.requested",
                    {
                        "tool": action.tool_call.name,
                        "args": action.tool_call.args,
                        "reason": decision.reason if decision else None,
                        "approver_hint": decision.approver_hint if decision else None,
                    },
                )
                self._checkpoint(run, "awaiting_approval")
                return run

            if result is not None:
                self._apply_tool_result(run, result)
                continue

        return run

    def resume_with_approval(self, run_id: str, approved: bool, approver: str) -> RunState:
        run = self.runs[run_id]
        if run.status != "awaiting_approval" or run.pending_tool_call is None:
            raise ValueError(f"run {run_id} is not waiting for approval")

        call = run.pending_tool_call
        run.approvals.append(
            {
                "tool_call_id": call.tool_call_id,
                "tool": call.name,
                "approved": approved,
                "approver": approver,
                "created_at": utc_now(),
            }
        )
        self._record_event(
            run,
            "approval.resolved",
            {"tool": call.name, "approved": approved, "approver": approver},
        )

        run.pending_tool_call = None
        run.status = "running"
        _mode, _decision, result = self.gateway.dispatch(run, call, approved=approved)
        if result is not None:
            self._apply_tool_result(run, result)
        self._checkpoint(run, "resumed_after_approval")
        return self.run_until_blocked_or_done(run_id)

    def latest_checkpoint(self, run_id: str) -> dict[str, Any]:
        return deepcopy(self.runs[run_id].checkpoints[-1])

    def _apply_tool_result(self, run: RunState, result: ToolResult) -> None:
        run.tool_results.append(result)
        self._record_event(
            run,
            "tool.result",
            {"tool": result.name, "ok": result.ok, "data": result.data, "error": result.error},
        )

        if result.name == "lookup_order" and result.ok:
            run.scratchpad["order"] = result.data
            run.messages.append(
                Message(role="tool", content=f"lookup_order returned {json.dumps(result.data)}")
            )
            return

        if result.name == "issue_refund" and result.ok:
            run.scratchpad["refund"] = result.data
            run.messages.append(
                Message(role="tool", content=f"issue_refund returned {json.dumps(result.data)}")
            )
            return

        if result.name == "issue_refund" and result.error == "denied_by_human":
            run.scratchpad["refund_denied"] = True
            run.messages.append(Message(role="tool", content="issue_refund was denied by human."))

    def _record_event(self, run: RunState, event_type: str, details: dict[str, Any]) -> None:
        run.events.append(
            RuntimeEvent(
                seq=len(run.events) + 1,
                event_type=event_type,
                run_id=run.run_id,
                step=run.turn,
                details=deepcopy(details),
                created_at=utc_now(),
            )
        )

    def _checkpoint(self, run: RunState, reason: str) -> None:
        run.checkpoints.append(
            {
                "seq": len(run.checkpoints) + 1,
                "reason": reason,
                "created_at": utc_now(),
                "snapshot": self._snapshot(run),
            }
        )

    def _snapshot(self, run: RunState) -> dict[str, Any]:
        return {
            "run_id": run.run_id,
            "status": run.status,
            "turn": run.turn,
            "agent": asdict(run.agent),
            "user_input": run.user_input,
            "messages": [asdict(message) for message in run.messages],
            "tool_results": [asdict(result) for result in run.tool_results],
            "scratchpad": deepcopy(run.scratchpad),
            "pending_tool_call": asdict(run.pending_tool_call) if run.pending_tool_call else None,
            "approvals": deepcopy(run.approvals),
            "final_output": run.final_output,
        }


def extract_order_id(text: str) -> str:
    for token in text.replace(",", " ").replace(".", " ").split():
        normalized = token.strip().upper()
        if normalized.startswith("ORD-"):
            return normalized
    return "ORD-1001"


def lookup_order(order_id: str) -> dict[str, Any]:
    orders = {
        "ORD-1001": {
            "order_id": "ORD-1001",
            "amount": 120,
            "currency": "USD",
            "delivery_status": "lost",
            "customer_tier": "gold",
        }
    }
    if order_id not in orders:
        raise ValueError(f"order not found: {order_id}")
    return deepcopy(orders[order_id])


def issue_refund(order_id: str, amount: int, reason: str) -> dict[str, Any]:
    return {
        "refund_id": f"RF-{order_id.split('-')[-1]}",
        "order_id": order_id,
        "amount": amount,
        "currency": "USD",
        "reason": reason,
        "status": "succeeded",
    }


def refund_approval_policy(_run: RunState, call: ToolCall) -> PolicyDecision:
    amount = int(call.args["amount"])
    if amount >= 50:
        return PolicyDecision(
            required=True,
            reason=f"refund_amount={amount} requires human approval",
            approver_hint="support_lead",
        )
    return PolicyDecision(required=False, reason="low_risk_refund")


def refund_idempotency_key(call: ToolCall) -> str:
    return f"refund:{call.args['order_id']}:{call.args['amount']}:{call.args['reason']}"


def build_runtime() -> AgentRuntime:
    gateway = ToolGateway()
    gateway.register(ToolSpec(name="lookup_order", func=lookup_order))
    gateway.register(
        ToolSpec(
            name="issue_refund",
            func=issue_refund,
            approval_policy=refund_approval_policy,
            idempotency_key=refund_idempotency_key,
        )
    )
    return AgentRuntime(model=MockRefundModel(), gateway=gateway)


def print_section(title: str) -> None:
    print(f"\n== {title} ==")


def main() -> None:
    agent = AgentSpec(
        agent_id="refund_agent",
        name="Refund Agent",
        instructions="Resolve refund requests safely. High-value refunds require approval.",
        tools=["lookup_order", "issue_refund"],
        max_turns=8,
    )
    runtime = build_runtime()

    run = runtime.create_run(agent, "Please refund order ORD-1001 because the package was lost.")
    runtime.run_until_blocked_or_done(run.run_id)

    print_section("Paused Run")
    print(f"status: {run.status}")
    print(f"pending_tool_call: {asdict(run.pending_tool_call) if run.pending_tool_call else None}")

    print_section("Latest Checkpoint")
    print(json.dumps(runtime.latest_checkpoint(run.run_id), indent=2, sort_keys=True))

    runtime.resume_with_approval(
        run_id=run.run_id,
        approved=True,
        approver="support_lead@example.com",
    )

    print_section("Final Run")
    print(f"status: {run.status}")
    print(f"final_output: {run.final_output}")

    print_section("Event Log")
    for event in run.events:
        print(
            f"{event.seq:02d} step={event.step} type={event.event_type} "
            f"details={json.dumps(event.details, sort_keys=True)}"
        )


if __name__ == "__main__":
    main()
