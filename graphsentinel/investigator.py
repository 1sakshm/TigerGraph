import math
import time
from datetime import datetime, timezone
from uuid import uuid4

from graphsentinel.graph import GraphPort
from graphsentinel.models import CaseRecord, Evidence, Neighborhood, Recommendation, TraceEvent
from graphsentinel.policy import PolicyEngine


def _entropy(probability: float) -> float:
    if probability in (0, 1):
        return 0.0
    return -(probability * math.log2(probability) + (1 - probability) * math.log2(1 - probability))


class Investigator:
    def __init__(self, graph: GraphPort, policy: PolicyEngine):
        self.graph = graph
        self.policy = policy

    def investigate(self, transaction_id: str, trigger: str) -> CaseRecord:
        if not transaction_id.strip() or not trigger.strip():
            raise ValueError("transaction_id and trigger are required")
        start = time.perf_counter()
        context = self.graph.neighborhood(transaction_id, limit=50)
        case = CaseRecord(
            id=f"CASE-{uuid4().hex[:12].upper()}",
            transaction_id=transaction_id,
            trigger=trigger,
            status="GRAPH_INVESTIGATION",
        )
        case.trace.append(TraceEvent(
            state="INITIAL_RETRIEVAL", tool="graph.neighborhood",
            reason="Retrieve the transaction, account history and shared-device paths",
            result=f"{len(context.account_history)} account transactions; {len(context.device_peers)} device peers",
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
        ))
        self._collect_graph_evidence(case, context)
        entities = {context.transaction.account_id, context.transaction.id}
        if context.transaction.device_id:
            entities.add(context.transaction.device_id)
        if case.patterns:
            start = time.perf_counter()
            case.related_cases = self.graph.prior_cases(entities)
            case.trace.append(TraceEvent(
                state="CASE_MEMORY_SEARCH", tool="graph.prior_cases",
                reason="Compare current entities with resolved cases after a graph pattern was found",
                result=f"{len(case.related_cases)} related cases",
                latency_ms=round((time.perf_counter() - start) * 1000, 2),
            ))
            for prior in case.related_cases:
                if prior.outcome == "confirmed_fraud":
                    self._add(case, "prior_confirmed_case",
                              f"Related resolved case {prior.id} was confirmed fraud; this is supporting context, not a label for this transaction",
                              [prior.id, *sorted(entities.intersection(prior.entity_ids))], 0.7, "TigerGraph case memory")
        self._assess(case, context)
        return case

    def add_evidence(self, case: CaseRecord, kind: str, value: str) -> CaseRecord:
        if kind != "customer_confirmation" or value not in {"confirmed", "denied"}:
            raise ValueError("Supported evidence: customer_confirmation = confirmed or denied")
        if any(e.kind == "customer_confirmation" for e in case.evidence):
            raise ValueError("Customer confirmation already recorded")
        context = self.graph.neighborhood(case.transaction_id, limit=50)
        self._add(case, kind, f"Analyst recorded customer response: transaction {value}",
                  [case.transaction_id, context.transaction.account_id], 0.95,
                  "analyst_recorded_customer_response")
        case.trace.append(TraceEvent(
            state="REASSESSMENT", reason="New customer response resolves the key identity uncertainty",
            result=f"Customer {value} transaction",
        ))
        self._assess(case, context)
        return case

    def decide(self, case: CaseRecord, decision: str, analyst_id: str) -> CaseRecord:
        if decision not in {"approve", "reject"} or not analyst_id.strip():
            raise PermissionError("A named analyst must approve or reject")
        proposed = case.recommendations[-1]
        if proposed.status != "pending_approval":
            raise ValueError("No action is pending approval")
        if decision == "approve":
            case.actions_taken.append(self.policy.execute(proposed.action, approved_by=analyst_id))
            proposed.status = "executed"
            case.status = "ACTION_SIMULATED"
        else:
            proposed.status = "rejected"
            case.status = "ANALYST_REJECTED"
        case.trace.append(TraceEvent(
            state="HUMAN_DECISION", reason=f"Policy {proposed.policy_reference} requires a named analyst",
            result=f"{decision} by {analyst_id}; action execution is simulated",
        ))
        case.updated_at = datetime.now(timezone.utc)
        return case

    def _add(self, case: CaseRecord, kind: str, claim: str, entities: list[str],
             strength: float, source: str) -> None:
        case.evidence.append(Evidence(
            id=f"E-{len(case.evidence) + 1:03d}", kind=kind, claim=claim,
            entity_ids=entities, strength=strength, source=source,
        ))

    def _collect_graph_evidence(self, case: CaseRecord, context: Neighborhood) -> None:
        seed = context.transaction
        if seed.model_score is not None:
            self._add(case, "model_score", f"Upstream fraud model score is {seed.model_score:.2f}",
                      [seed.id], seed.model_score, "transaction model score")
        if seed.device_id and context.account_history and all(
            t.device_id != seed.device_id for t in context.account_history
        ):
            self._add(case, "new_device", "This device is absent from the account's available transaction history",
                      [seed.id, seed.account_id, seed.device_id], 0.7, "TigerGraph account history")
            case.patterns.append("new_device")
        peer_accounts = sorted({p.account_id for p in context.device_peers})
        if peer_accounts:
            self._add(case, "shared_device",
                      f"Device {seed.device_id} is used by {len(peer_accounts)} other accounts in the retrieved graph",
                      [seed.id, seed.device_id, *peer_accounts], min(0.95, 0.55 + 0.1 * len(peer_accounts)),
                      "TigerGraph device traversal")
            case.patterns.append("shared_device_cluster")
        if context.account_history:
            baseline = sorted(t.amount for t in context.account_history)
            median = baseline[len(baseline) // 2]
            if median > 0 and seed.amount >= 3 * median:
                self._add(case, "amount_anomaly",
                          f"Amount {seed.amount:.2f} is at least three times the available account median {median:.2f}",
                          [seed.id, *[t.id for t in context.account_history[:5]]], 0.65,
                          "TigerGraph account history")
                case.patterns.append("amount_anomaly")
        case.trace.append(TraceEvent(
            state="PATTERN_ANALYSIS", reason="Apply inspectable graph motif rules",
            result=f"{len(case.patterns)} patterns; {len(case.evidence)} evidence items",
        ))
        nodes = {seed.id: "Transaction", seed.account_id: "Account"}
        edges = [[seed.account_id, seed.id, "PERFORMED"]]
        if seed.device_id:
            nodes[seed.device_id] = "Device"
            edges.append([seed.id, seed.device_id, "USED_DEVICE"])
        for peer in context.device_peers:
            nodes[peer.account_id] = "Account"
            nodes[peer.transaction_id] = "Transaction"
            edges.extend([[peer.account_id, peer.transaction_id, "PERFORMED"],
                          [peer.transaction_id, peer.device_id, "USED_DEVICE"]])
        case.graph = {"nodes": [{"id": key, "type": value} for key, value in nodes.items()],
                      "edges": [{"source": a, "target": b, "type": c} for a, b, c in edges]}

    def _assess(self, case: CaseRecord, context: Neighborhood) -> None:
        kinds = {e.kind for e in case.evidence}
        score = context.transaction.model_score or 0.0
        risk = 0.08 + 0.4 * score
        risk += 0.15 if "new_device" in kinds else 0
        risk += 0.18 if "shared_device" in kinds else 0
        risk += 0.1 if "amount_anomaly" in kinds else 0
        risk += 0.1 if "prior_confirmed_case" in kinds else 0
        response = next((e.claim for e in case.evidence if e.kind == "customer_confirmation"), "")
        if "denied" in response:
            risk = max(risk, 0.95)
        elif "confirmed" in response:
            risk = min(risk, 0.18)
        confidence = min(0.74, 0.36 + 0.07 * len(kinds))
        if response:
            confidence = 0.95
        case.risk = round(min(1.0, risk), 3)
        case.confidence = round(confidence, 3)
        takeover = round(case.risk * (0.78 if "new_device" in kinds else 0.5), 3)
        case.hypotheses = {"account_takeover": takeover,
                           "other_fraud": round(max(0, case.risk - takeover), 3),
                           "legitimate_activity": round(1 - case.risk, 3)}
        case.missing_evidence = [] if response else ["customer_confirmation", "verified_device_history"]
        case.trace.append(TraceEvent(
            state="UNCERTAINTY_ASSESSMENT",
            reason="Separate suspiciousness from completeness of evidence; confidence is a heuristic, not calibrated probability",
            result=f"risk={case.risk:.3f}; confidence={case.confidence:.3f}",
        ))
        if "denied" in response:
            action = "BLOCK_CARD"
            reason = "Customer denial plus linked graph evidence supports a protective card block; analyst approval is required."
        elif "confirmed" in response:
            action = "MONITOR_ACCOUNT"
            reason = "Customer confirmation reduces immediate fraud risk; continue monitoring the related device cluster."
        elif case.risk >= 0.5:
            candidates = {
                "customer_confirmation": (1 - case.confidence) * 0.9 * _entropy(case.risk),
                "verified_device_history": (1 - case.confidence) * 0.55 * _entropy(case.risk),
            }
            best = max(candidates, key=candidates.get)
            action = "REQUEST_CUSTOMER_CONFIRMATION" if best == "customer_confirmation" else "REQUEST_STEP_UP_AUTHENTICATION"
            reason = (f"Risk is elevated but confidence is {case.confidence:.0%}. "
                      f"{best.replace('_', ' ').title()} has the highest estimated information value "
                      f"({candidates[best]:.3f}); confirmation supports monitoring, denial supports a block proposal.")
            case.trace.append(TraceEvent(
                state="EVIDENCE_REQUEST", reason="Select the evidence with greatest heuristic expected entropy reduction",
                result=f"{best}: {candidates[best]:.3f}",
            ))
        else:
            action = "MONITOR_ACCOUNT"
            reason = "Available graph evidence does not justify a high impact intervention."
        gate = self.policy.evaluate(action)
        if not gate.allowed:
            raise PermissionError(f"Policy denied {action}")
        status = "pending_approval" if gate.approval_required else "proposed"
        recommendation = Recommendation(
            action=action, reason=reason, evidence_ids=[e.id for e in case.evidence],
            risk=case.risk, confidence=case.confidence, policy_reference=gate.reference,
            approval_required=gate.approval_required, status=status,
        )
        case.recommendations.append(recommendation)
        case.status = ("APPROVAL_REQUIRED" if gate.approval_required else
                       "WAITING_FOR_EVIDENCE" if action.startswith("REQUEST_") else "RECOMMENDATION_READY")
        case.updated_at = datetime.now(timezone.utc)
        case.trace.append(TraceEvent(
            state="ACTION_SELECTION", reason="Apply deterministic policy to evidence based proposal",
            result=f"{action}; {status}; {gate.reference}",
        ))
