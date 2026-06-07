"""End-to-end multi-agent state management demo.

Run:
    python3 examples/multi_agent_state_demo.py

This example intentionally uses deterministic Python functions instead of LLM
calls. The goal is to expose the real state-management logic that sits under a
multi-agent application:

- state catalog and field-level permissions
- context views per agent
- state patches with version checks
- artifact references
- event log
- A2A-style context envelope
- remote result import
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pprint import pprint
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_path(path: str) -> list[str]:
    if not path.startswith("/"):
        raise ValueError(f"JSON path must start with '/': {path}")
    if path == "/":
        return []
    return [part for part in path.strip("/").split("/") if part]


def path_matches(prefix: str, path: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def get_value(root: Any, path: str) -> Any:
    current = root
    for token in parse_path(path):
        if isinstance(current, list):
            current = current[int(token)]
        else:
            current = current[token]
    return current


def resolve_parent(root: Any, path: str) -> tuple[Any, str]:
    tokens = parse_path(path)
    if not tokens:
        raise ValueError("Cannot resolve parent for root path")

    current = root
    for token in tokens[:-1]:
        if isinstance(current, list):
            current = current[int(token)]
        else:
            current = current[token]
    return current, tokens[-1]


def set_value(root: Any, path: str, value: Any) -> None:
    parent, last = resolve_parent(root, path)
    if isinstance(parent, list):
        parent[int(last)] = value
    else:
        parent[last] = value


def add_value(root: Any, path: str, value: Any) -> None:
    parent, last = resolve_parent(root, path)
    if isinstance(parent, list):
        if last == "-":
            parent.append(value)
        else:
            parent.insert(int(last), value)
    else:
        parent[last] = value


@dataclass(frozen=True)
class FieldRule:
    prefix: str
    readers: set[str]
    writers: set[str]
    consistency: str
    requires_evidence: bool = False

    def can_read(self, agent: str) -> bool:
        return "*" in self.readers or agent in self.readers

    def can_write(self, agent: str) -> bool:
        return agent in self.writers


@dataclass
class Artifact:
    artifact_id: str
    kind: str
    producer: str
    summary: str
    data: dict[str, Any]
    version: int = 1

    def ref(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "kind": self.kind,
            "producer": self.producer,
            "summary": self.summary,
            "version": self.version,
        }


@dataclass
class PatchOperation:
    op: str
    path: str
    value: Any


@dataclass
class StatePatch:
    patch_id: str
    actor: str
    base_state_version: int
    evidence_refs: list[str]
    operations: list[PatchOperation]
    confidence: float = 1.0


@dataclass
class Event:
    event_id: str
    event_type: str
    actor: str
    state_version: int
    details: dict[str, Any]
    created_at: str


class RejectedPatch(Exception):
    pass


class StateStore:
    def __init__(self, state: dict[str, Any], catalog: list[FieldRule]):
        self.state = deepcopy(state)
        self.catalog = catalog
        self.version = 1
        self.artifacts: dict[str, Artifact] = {}
        self.events: list[Event] = []
        self._event_seq = 0

    def create_artifact(
        self,
        artifact_id: str,
        kind: str,
        producer: str,
        summary: str,
        data: dict[str, Any],
    ) -> Artifact:
        artifact = Artifact(
            artifact_id=artifact_id,
            kind=kind,
            producer=producer,
            summary=summary,
            data=data,
        )
        self.artifacts[artifact_id] = artifact
        self.record_event(
            event_type="artifact.created",
            actor=producer,
            details={"artifact": artifact.ref()},
        )
        return artifact

    def build_context_view(self, agent: str) -> dict[str, Any]:
        view = self._filter_for_reader(agent, "", self.state)
        return {
            "context_view_id": f"ctx_{agent}_v{self.version}",
            "agent": agent,
            "state_version": self.version,
            "state": view,
            "artifact_index": {
                artifact_id: artifact.ref()
                for artifact_id, artifact in sorted(self.artifacts.items())
            },
        }

    def apply_patch(self, patch: StatePatch) -> None:
        if patch.base_state_version != self.version:
            raise RejectedPatch(
                f"stale patch {patch.patch_id}: base={patch.base_state_version}, current={self.version}"
            )

        self._validate_patch(patch)

        for operation in patch.operations:
            self._apply_operation(operation)

        self.version += 1
        self.record_event(
            event_type="state.patch.committed",
            actor=patch.actor,
            details={
                "patch_id": patch.patch_id,
                "base_state_version": patch.base_state_version,
                "new_state_version": self.version,
                "operations": [
                    {"op": op.op, "path": op.path, "value": op.value}
                    for op in patch.operations
                ],
                "evidence_refs": patch.evidence_refs,
                "confidence": patch.confidence,
            },
        )

    def record_event(self, event_type: str, actor: str, details: dict[str, Any]) -> None:
        self._event_seq += 1
        self.events.append(
            Event(
                event_id=f"evt_{self._event_seq:03d}",
                event_type=event_type,
                actor=actor,
                state_version=self.version,
                details=details,
                created_at=utc_now(),
            )
        )

    def _validate_patch(self, patch: StatePatch) -> None:
        for operation in patch.operations:
            rule = self._find_rule(operation.path)
            if rule is None:
                raise RejectedPatch(f"no catalog rule for path {operation.path}")
            if not rule.can_write(patch.actor):
                raise RejectedPatch(
                    f"{patch.actor} cannot write {operation.path}; owner rule is {rule.prefix}"
                )
            if rule.requires_evidence and not patch.evidence_refs:
                raise RejectedPatch(f"{operation.path} requires evidence_refs")

        for evidence_ref in patch.evidence_refs:
            artifact_id = evidence_ref.replace("artifact:", "", 1)
            if artifact_id not in self.artifacts:
                raise RejectedPatch(
                    f"evidence artifact {artifact_id} does not exist for patch {patch.patch_id}"
                )

    def _apply_operation(self, operation: PatchOperation) -> None:
        if operation.op == "replace":
            set_value(self.state, operation.path, deepcopy(operation.value))
            return

        if operation.op == "add":
            if path_matches("/risks/register", operation.path):
                self._append_or_merge_by_id("/risks/register", operation.value)
                return
            add_value(self.state, operation.path, deepcopy(operation.value))
            return

        raise RejectedPatch(f"unsupported operation {operation.op}")

    def _append_or_merge_by_id(self, list_path: str, item: dict[str, Any]) -> None:
        items = get_value(self.state, list_path)
        for index, existing in enumerate(items):
            if existing.get("id") == item.get("id"):
                merged = {
                    **existing,
                    **item,
                    "evidence_refs": sorted(
                        set(existing.get("evidence_refs", []) + item.get("evidence_refs", []))
                    ),
                    "confidence": max(
                        existing.get("confidence", 0),
                        item.get("confidence", 0),
                    ),
                }
                items[index] = merged
                return
        items.append(deepcopy(item))

    def _filter_for_reader(self, agent: str, path: str, value: Any) -> Any:
        rule = self._find_rule(path) if path else None
        if rule and rule.can_read(agent):
            return deepcopy(value)

        if isinstance(value, dict):
            result = {}
            for key, child in value.items():
                child_path = f"{path}/{key}" if path else f"/{key}"
                filtered = self._filter_for_reader(agent, child_path, child)
                if filtered is not None:
                    result[key] = filtered
            return result if result else None

        if isinstance(value, list):
            rule = self._find_rule(path)
            if rule and rule.can_read(agent):
                return deepcopy(value)
            return None

        return None

    def _find_rule(self, path: str) -> FieldRule | None:
        matches = [rule for rule in self.catalog if path_matches(rule.prefix, path)]
        if not matches:
            return None
        return max(matches, key=lambda rule: len(rule.prefix))


def build_catalog() -> list[FieldRule]:
    all_task_agents = {
        "hr_agent",
        "security_agent",
        "it_agent",
        "supervisor",
        "human_manager",
        "a2a_importer",
    }

    return [
        FieldRule(
            prefix="/task",
            readers=all_task_agents,
            writers={"hr_agent", "supervisor"},
            consistency="strong",
        ),
        FieldRule(
            prefix="/employee",
            readers={"hr_agent", "security_agent", "it_agent", "supervisor", "a2a_importer"},
            writers={"hr_agent"},
            consistency="strong",
        ),
        FieldRule(
            prefix="/subtasks/hr_profile",
            readers=all_task_agents,
            writers={"hr_agent"},
            consistency="strong",
        ),
        FieldRule(
            prefix="/subtasks/security_review",
            readers=all_task_agents,
            writers={"security_agent"},
            consistency="strong",
        ),
        FieldRule(
            prefix="/subtasks/it_account",
            readers=all_task_agents,
            writers={"it_agent", "a2a_importer"},
            consistency="strong",
        ),
        FieldRule(
            prefix="/risks/register",
            readers={"security_agent", "supervisor", "human_manager"},
            writers={"security_agent"},
            consistency="eventual",
            requires_evidence=True,
        ),
        FieldRule(
            prefix="/approvals/pending",
            readers={"security_agent", "supervisor", "human_manager", "a2a_importer"},
            writers={"security_agent", "human_manager"},
            consistency="strong",
        ),
        FieldRule(
            prefix="/approvals/history",
            readers=all_task_agents,
            writers={"security_agent", "human_manager"},
            consistency="immutable",
        ),
        FieldRule(
            prefix="/artifacts/references",
            readers=all_task_agents,
            writers={"hr_agent", "security_agent", "it_agent", "a2a_importer"},
            consistency="immutable",
        ),
        FieldRule(
            prefix="/final_message",
            readers=all_task_agents,
            writers={"supervisor"},
            consistency="strong",
        ),
    ]


def build_initial_state() -> dict[str, Any]:
    return {
        "task": {
            "id": "onboarding_001",
            "goal": "Onboard Alice into the Finance department",
            "status": "submitted",
        },
        "employee": {
            "name": "Alice",
            "department": "Finance",
            "manager": "Bob",
            "start_date": "2026-07-01",
        },
        "subtasks": {
            "hr_profile": {"owner": "hr_agent", "status": "pending"},
            "security_review": {"owner": "security_agent", "status": "pending"},
            "it_account": {"owner": "it_agent", "status": "pending"},
        },
        "risks": {"register": []},
        "approvals": {"pending": [], "history": []},
        "artifacts": {"references": []},
        "final_message": None,
    }


class HRAgent:
    name = "hr_agent"

    def run(self, store: StateStore) -> None:
        context = store.build_context_view(self.name)
        artifact = store.create_artifact(
            artifact_id="hr_form_v1",
            kind="form",
            producer=self.name,
            summary="HR onboarding form for Alice",
            data={"employee_name": "Alice", "department": "Finance", "manager": "Bob"},
        )
        patch = StatePatch(
            patch_id="patch_hr_profile_completed",
            actor=self.name,
            base_state_version=context["state_version"],
            evidence_refs=[],
            operations=[
                PatchOperation("replace", "/subtasks/hr_profile/status", "completed"),
                PatchOperation("replace", "/task/status", "working"),
                PatchOperation("add", "/artifacts/references/-", artifact.ref()),
            ],
        )
        store.apply_patch(patch)


class SecurityAgent:
    name = "security_agent"

    def run(self, store: StateStore) -> None:
        context = store.build_context_view(self.name)
        state = context["state"]
        employee = state["employee"]
        approval_history = state["approvals"]["history"]

        finance_approval_exists = any(
            item.get("type") == "finance_role_access" and item.get("status") == "approved"
            for item in approval_history
        )

        if employee["department"] == "Finance" and not finance_approval_exists:
            policy_artifact = store.create_artifact(
                artifact_id="security_policy_finance_access",
                kind="policy",
                producer=self.name,
                summary="Finance department access requires manager approval",
                data={"rule": "finance_role_access_requires_manager_approval"},
            )
            patch = StatePatch(
                patch_id="patch_security_requires_approval",
                actor=self.name,
                base_state_version=context["state_version"],
                evidence_refs=[f"artifact:{policy_artifact.artifact_id}"],
                operations=[
                    PatchOperation("replace", "/subtasks/security_review/status", "input_required"),
                    PatchOperation(
                        "add",
                        "/risks/register/-",
                        {
                            "id": "risk_finance_access_approval",
                            "severity": "medium",
                            "status": "waiting_for_approval",
                            "description": "Finance role requires manager approval before IT account provisioning",
                            "evidence_refs": [f"artifact:{policy_artifact.artifact_id}"],
                            "confidence": 0.98,
                        },
                    ),
                    PatchOperation(
                        "replace",
                        "/approvals/pending",
                        [
                            {
                                "id": "approval_finance_access",
                                "type": "finance_role_access",
                                "requested_by": self.name,
                                "status": "pending",
                            }
                        ],
                    ),
                ],
                confidence=0.98,
            )
            store.apply_patch(patch)
            return

        patch = StatePatch(
            patch_id="patch_security_completed",
            actor=self.name,
            base_state_version=context["state_version"],
            evidence_refs=["artifact:security_policy_finance_access"],
            operations=[
                PatchOperation("replace", "/subtasks/security_review/status", "completed"),
                PatchOperation(
                    "add",
                    "/risks/register/-",
                    {
                        "id": "risk_finance_access_approval",
                        "severity": "low",
                        "status": "mitigated",
                        "description": "Manager approval exists, so Finance access can be provisioned",
                        "evidence_refs": ["artifact:security_policy_finance_access"],
                        "confidence": 0.99,
                    },
                ),
            ],
        )
        store.apply_patch(patch)


class HumanManager:
    name = "human_manager"

    def approve_finance_access(self, store: StateStore) -> None:
        context = store.build_context_view(self.name)
        patch = StatePatch(
            patch_id="patch_manager_approval",
            actor=self.name,
            base_state_version=context["state_version"],
            evidence_refs=[],
            operations=[
                PatchOperation("replace", "/approvals/pending", []),
                PatchOperation(
                    "add",
                    "/approvals/history/-",
                    {
                        "id": "approval_finance_access",
                        "type": "finance_role_access",
                        "status": "approved",
                        "approved_by": "Bob",
                    },
                ),
            ],
        )
        store.apply_patch(patch)


def build_a2a_context_envelope(store: StateStore) -> dict[str, Any]:
    context = store.build_context_view("a2a_importer")
    state = context["state"]
    approval_history = state["approvals"]["history"]

    return {
        "schema_version": "1.0",
        "caller_task_id": state["task"]["id"],
        "context_id": "employee_alice_onboarding",
        "trace_id": "trace_onboarding_001",
        "state_version": context["state_version"],
        "goal": "Provision an IT account and laptop for Alice",
        "employee": {
            "name": state["employee"]["name"],
            "department": state["employee"]["department"],
            "manager": state["employee"]["manager"],
        },
        "approval_summary": [
            {
                "type": item["type"],
                "status": item["status"],
                "approved_by": item.get("approved_by"),
            }
            for item in approval_history
        ],
        "constraints": [
            "Do not access payroll data",
            "Provision Finance access only if manager approval exists",
        ],
        "return_contract": {
            "expected_data_fields": ["account_status", "ticket_id"],
            "expected_artifacts": ["it_ticket"],
        },
    }


class RemoteITAgent:
    name = "remote_it_agent"

    def handle_task(self, envelope: dict[str, Any]) -> dict[str, Any]:
        approvals = envelope["approval_summary"]
        finance_access_approved = any(
            item["type"] == "finance_role_access" and item["status"] == "approved"
            for item in approvals
        )

        if not finance_access_approved:
            return {
                "remote_task_id": "a2a_it_task_001",
                "status": "input-required",
                "input_request": {
                    "reason": "Finance access requires manager approval",
                    "required_approval_type": "finance_role_access",
                },
            }

        return {
            "remote_task_id": "a2a_it_task_001",
            "status": "completed",
            "data": {
                "account_status": "completed",
                "ticket_id": "IT-4242",
            },
            "artifact": {
                "artifact_id": "remote_it_ticket_4242",
                "kind": "ticket",
                "producer": self.name,
                "summary": "IT account and laptop ticket for Alice",
                "data": {
                    "ticket_id": "IT-4242",
                    "account": "alice.finance.example",
                    "laptop": "standard-finance-laptop",
                },
            },
        }


def import_a2a_result(store: StateStore, result: dict[str, Any]) -> None:
    if result["status"] != "completed":
        store.record_event(
            event_type="a2a.input_required",
            actor="a2a_importer",
            details=result,
        )
        return

    remote_artifact = result["artifact"]
    local_artifact = store.create_artifact(
        artifact_id="local_copy_remote_it_ticket_4242",
        kind=remote_artifact["kind"],
        producer="a2a_importer",
        summary=remote_artifact["summary"],
        data={
            "remote_task_id": result["remote_task_id"],
            "remote_artifact_id": remote_artifact["artifact_id"],
            "payload": remote_artifact["data"],
        },
    )

    context = store.build_context_view("a2a_importer")
    patch = StatePatch(
        patch_id="patch_import_it_result",
        actor="a2a_importer",
        base_state_version=context["state_version"],
        evidence_refs=[],
        operations=[
            PatchOperation("replace", "/subtasks/it_account/status", result["data"]["account_status"]),
            PatchOperation(
                "add",
                "/artifacts/references/-",
                {
                    **local_artifact.ref(),
                    "remote_task_id": result["remote_task_id"],
                },
            ),
        ],
    )
    store.apply_patch(patch)


class Supervisor:
    name = "supervisor"

    def run(self, store: StateStore) -> None:
        context = store.build_context_view(self.name)
        state = context["state"]
        statuses = {
            name: value["status"]
            for name, value in state["subtasks"].items()
        }

        if all(status == "completed" for status in statuses.values()):
            message = "Onboarding completed: HR profile, security review, and IT account are done."
            task_status = "completed"
        else:
            message = f"Onboarding still in progress: {statuses}"
            task_status = "working"

        patch = StatePatch(
            patch_id="patch_supervisor_summary",
            actor=self.name,
            base_state_version=context["state_version"],
            evidence_refs=[],
            operations=[
                PatchOperation("replace", "/task/status", task_status),
                PatchOperation("replace", "/final_message", message),
            ],
        )
        store.apply_patch(patch)


def print_step(title: str, payload: Any) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)
    pprint(payload, sort_dicts=False)


def main() -> None:
    store = StateStore(build_initial_state(), build_catalog())
    hr_agent = HRAgent()
    security_agent = SecurityAgent()
    manager = HumanManager()
    remote_it_agent = RemoteITAgent()
    supervisor = Supervisor()

    print_step("Initial supervisor context", store.build_context_view("supervisor"))

    hr_agent.run(store)
    print_step("After HR patch", store.state)

    first_envelope = build_a2a_context_envelope(store)
    first_remote_result = remote_it_agent.handle_task(first_envelope)
    import_a2a_result(store, first_remote_result)
    print_step("First A2A call result before approval", first_remote_result)

    security_agent.run(store)
    print_step("After security asks for approval", store.state)

    manager.approve_finance_access(store)
    print_step("After manager approval", store.state)

    security_agent.run(store)
    print_step("After security completion", store.state)

    second_envelope = build_a2a_context_envelope(store)
    second_remote_result = remote_it_agent.handle_task(second_envelope)
    import_a2a_result(store, second_remote_result)
    print_step("Second A2A call result after approval", second_remote_result)

    supervisor.run(store)
    print_step("Final state", store.state)
    print_step("Event log", [event.__dict__ for event in store.events])


if __name__ == "__main__":
    main()
