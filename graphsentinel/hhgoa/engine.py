"""Bounded, evidence-cited HHGOA benchmark investigation.

The local query port is for reproducible development. It never reports a graph
write. The same evidence and policy contract is intended for GSQL query results.
"""

from datetime import datetime
import time

from graphsentinel.hhgoa.contracts import (
    Action, Answer, CasePart, EvidenceItem, EvidenceRequest, NextActions, Sar,
)
from graphsentinel.hhgoa.dataset import DatasetQueries
from graphsentinel.hhgoa.policy import make_action, validate_actions


def _profile(row: dict) -> str:
    fields = [row.get(key) for key in ("device_info", "os", "browser", "screen")]
    return " | ".join(value or "unknown" for value in fields)


def _seconds_between(a: str, b: str) -> float:
    return abs((datetime.fromisoformat(a) - datetime.fromisoformat(b)).total_seconds())


def _different_customers(peers: list[dict], customer_id: str) -> list[dict]:
    return [peer for peer in peers if peer["customer_id"] != customer_id]


class BenchmarkInvestigator:
    def __init__(self, data: DatasetQueries):
        self.data = data
        self.last_trace: list[dict] = []

    def _ref(self, operation: str) -> str:
        if self.data.source != "graph":
            return f"index:{operation}"
        queries = {
            "transaction": "hh_transaction_context",
            "identity_status": "hh_transaction_context",
            "identity_proxy": "hh_transaction_context",
            "customer_history_30d": "hh_customer_window",
            "customer_window_6h": "hh_customer_window",
            "card_testing_window": "hh_customer_window",
            "region_baseline": "hh_customer_window",
            "profile_neighbors_7d": "hh_profile_neighbors",
            "corroborated_profile_cluster": "hh_profile_neighbors",
            "known_cards_on_peer_customers": "hh_prior_cases",
            "prior_customer_cases": "hh_prior_cases",
        }
        return f"query:{queries[operation]}:{operation}"

    def investigate(self, trigger: dict) -> Answer:
        started = time.perf_counter()
        call_start = self.data.calls
        self.last_trace = []
        seed = self.data.transaction(trigger["flagged_txn_id"])
        if seed["customer_id"] != trigger["customer_id"]:
            raise ValueError("Case pack and transaction customer IDs disagree")
        self._trace("transaction", seed["id"], "Retrieve flagged transaction and identity")
        stats = self.data.history_stats(seed["customer_id"], seed["ts"], seed["addr1"])
        window = self.data.customer_window(seed["customer_id"], seed["ts"],
                                           trigger["opened_at"], hours=48)
        self._trace("customer_window", seed["customer_id"],
                    f"{len(window)} transactions in the bounded 48-hour window")
        peers = self.data.profile_peers(seed, trigger["opened_at"])
        other_peers = _different_customers(peers, seed["customer_id"])
        self._trace("profile_peers", seed["id"],
                    f"{len({p['customer_id'] for p in other_peers})} other customers")
        prior = self.data.prior_cases(seed["customer_id"], trigger["opened_at"])
        self._trace("prior_cases", seed["customer_id"], f"{len(prior)} closed cases")

        evidence: list[EvidenceItem] = []
        evidence.append(EvidenceItem(
            claim=(f"Transaction {seed['id']} for customer {seed['customer_id']} was "
                   f"${seed['amount']:.2f} via {seed['channel']} at {seed['ts']}; "
                   f"upstream model score {seed['risk']:.2f}."),
            source=self.data.source, ref=self._ref("transaction"), entity_ids=[seed["id"], seed["customer_id"]],
        ))
        report = trigger["trigger_type"] == "customer_report"
        if report:
            evidence.append(EvidenceItem(
                claim=f"Customer report disputes transaction {seed['id']}: {trigger['trigger_text']}",
                source="customer", ref=f"case_pack:{trigger['case_id']}:trigger_text",
                entity_ids=[seed["id"], seed["customer_id"]],
            ))
        if seed.get("identity_status") == "New":
            evidence.append(EvidenceItem(
                claim=f"Identity record marks the device as New for transaction {seed['id']}.",
                source=self.data.source, ref=self._ref("identity_status"), entity_ids=[seed["id"]],
            ))
        if seed.get("proxy_status"):
            evidence.append(EvidenceItem(
                claim=f"Identity proxy attribute is {seed['proxy_status']} for transaction {seed['id']}.",
                source=self.data.source, ref=self._ref("identity_proxy"), entity_ids=[seed["id"]],
            ))
        if stats["count"] >= 8:
            evidence.append(EvidenceItem(
                claim=(f"In the prior 30 days this customer group had {stats['count']} transactions, "
                       f"median amount ${stats['median_amount']:.2f}, and "
                       f"{stats['region_count']} in billing region {seed['addr1'] or 'missing'}.") ,
                source=self.data.source, ref=self._ref("customer_history_30d"), entity_ids=[seed["customer_id"]],
            ))

        nearby = [row for row in window if row["id"] != seed["id"] and
                  row["product"] == seed["product"] and row["channel"] == seed["channel"] and
                  _seconds_between(row["ts"], seed["ts"]) <= 6 * 3600]
        amount_peers = [row for row in nearby if seed["amount"] > 0 and
                        abs(row["amount"] - seed["amount"]) / seed["amount"] <= 0.16]
        if len(amount_peers) >= 2:
            ids = [seed["id"], *[row["id"] for row in amount_peers[:5]]]
            evidence.append(EvidenceItem(
                claim=(f"At least {len(amount_peers) + 1} same-customer, same-product, "
                       f"similar-amount transactions occurred within six hours of {seed['id']}; "
                       "the source does not identify which physical card made each one."),
                source=self.data.source, ref=self._ref("customer_window_6h"), entity_ids=ids,
            ))
        tiny = [row for row in nearby if row["amount"] <= 7.5 and
                row["channel"] == "online" and row["ts"] < seed["ts"] and
                _seconds_between(row["ts"], seed["ts"]) <= 3600]
        testing = seed["amount"] > 20 and len(tiny) >= 3
        if testing:
            evidence.append(EvidenceItem(
                claim=(f"Three or more small online authorizations preceded the "
                       f"${seed['amount']:.2f} transaction within one hour."),
                source=self.data.source, ref=self._ref("card_testing_window"), entity_ids=[row["id"] for row in tiny[:8]] + [seed["id"]],
            ))
        region_novel = (seed["channel"] == "in_person" and seed["addr1"] and
                        stats["count"] >= 10 and stats["region_count"] <= 1 and
                        stats["distinct_regions"] <= 5)
        if region_novel:
            evidence.append(EvidenceItem(
                claim=(f"In-person purchase in billing region {seed['addr1']} is absent or nearly "
                       "absent from the prior 30-day customer history."),
                source=self.data.source, ref=self._ref("region_baseline"), entity_ids=[seed["id"], seed["customer_id"]],
            ))

        peer_customers = sorted({peer["customer_id"] for peer in other_peers})
        known_cards = self.data.known_cards(peer_customers, trigger["opened_at"])
        detailed_profile = sum(bool(seed.get(k)) for k in ("device_info", "os", "browser", "screen")) >= 3
        matching_amount = [peer for peer in other_peers if seed["amount"] > 0 and
                           abs(peer["amount"] - seed["amount"]) / seed["amount"] <= 0.12 and
                           peer["product"] == seed["product"]]
        same_email = [peer for peer in matching_amount if
                      peer["email"] == seed["email"] and
                      peer["recipient_email"] == seed["recipient_email"]]
        corroborated_amount = len({p["customer_id"] for p in same_email}) >= 2
        analyst_cluster = (trigger["trigger_type"] == "analyst_request" and
                           seed.get("proxy_status") == "IP_PROXY:ANONYMOUS" and
                           len(peer_customers) >= 5 and
                           sum(peer.get("identity_status") == "New" for peer in other_peers) >= 5)
        coordinated = detailed_profile and (corroborated_amount or analyst_cluster)
        if peer_customers:
            ids = [seed["id"], *[peer["id"] for peer in other_peers[:8]], *peer_customers[:8]]
            evidence.append(EvidenceItem(
                claim=(f"Detailed device profile {_profile(seed)} appears on transactions for "
                       f"{len(peer_customers)} other customers in the prior seven days. "
                       "A shared profile alone does not prove a shared physical device."),
                source=self.data.source, ref=self._ref("profile_neighbors_7d"), entity_ids=ids,
            ))
        if coordinated:
            ids = [seed["id"], *[peer["id"] for peer in matching_amount[:8]]]
            if analyst_cluster:
                claim = ("Analyst-reported shared-origin activity is corroborated by at least five "
                         "other customer groups using the same detailed profile, New identity "
                         "status, and anonymous proxy context in the prior seven days.")
                ids = [seed["id"], *[peer["id"] for peer in other_peers[:8]]]
            else:
                claim = ("At least two other customer groups used the same detailed device "
                         "profile, product, purchaser email domain, recipient email domain, "
                         f"and near-${seed['amount']:.2f} amount in seven days.")
                ids = [seed["id"], *[peer["id"] for peer in same_email[:8]]]
            evidence.append(EvidenceItem(claim=claim, source=self.data.source,
                                         ref=self._ref("corroborated_profile_cluster"), entity_ids=ids))
            if known_cards:
                evidence.append(EvidenceItem(
                    claim=(f"Closed-case records identify {len(known_cards)} card IDs for customer "
                           "groups sharing the profile; exact card-to-peer-transaction attribution "
                           "is unavailable in the supplied transaction CSV."),
                    source=self.data.source, ref=self._ref("known_cards_on_peer_customers"),
                    entity_ids=[row["card_id"] for row in known_cards],
                ))
        relevant_prior = [p for p in prior if p["outcome"] == "confirmed_fraud"][:2]
        cleared_prior = next((p for p in prior if p["outcome"] == "cleared"), None)
        used_prior = relevant_prior[:1] + ([cleared_prior] if cleared_prior else [])
        if used_prior:
            evidence.append(EvidenceItem(
                claim=("Closed case memory for this customer group contains " + ", ".join(
                    f"{p['case_id']} ({p['outcome']}, {p['pattern']})" for p in used_prior
                ) + "; these outcomes are context, not a verdict on the current transaction."),
                source=self.data.source, ref=self._ref("prior_customer_cases"), entity_ids=[p["case_id"] for p in used_prior],
            ))

        # This score is an inspectable investigation heuristic, not a calibrated model.
        probability = 0.10 + 0.53 * (seed["risk"] or 0)
        probability += 0.32 if report else 0
        probability += 0.10 if seed["identity_status"] == "New" else 0
        probability += 0.14 if len(amount_peers) >= 2 else 0
        probability += 0.18 if region_novel else 0
        probability += 0.35 if coordinated else 0
        probability += 0.25 if analyst_cluster else 0
        probability += 0.19 if testing else 0
        if stats["count"] >= 20 and seed["addr1"] and stats["region_count"] >= 10:
            probability -= 0.12
        if stats["median_amount"] and seed["amount"] > 4 * stats["median_amount"]:
            probability += 0.09
        if cleared_prior and not relevant_prior:
            probability -= 0.05
        probability = round(max(0.06, min(0.96, probability)), 3)

        if coordinated:
            pattern = "undocumented"
            description = ("Several customer groups made similar online purchases from one detailed "
                           "device profile in a short window. This cross-customer amount and device "
                           "motif is visible through profile-neighbor and transaction-window queries.")
        elif testing:
            pattern, description = "card_testing", ""
        elif region_novel:
            pattern, description = "out_of_region_use", ""
        elif seed["channel"] == "online" and seed["identity_status"] == "New":
            pattern, description = "card_not_present_new_device", ""
        elif seed["channel"] == "online" and (len(amount_peers) >= 2 or probability >= 0.67):
            pattern, description = "card_not_present_fraud", ""
        else:
            pattern, description = "none", ""

        # Only assert a multi-transaction episode when the supporting motif is strong.
        episode = [seed]
        if probability >= 0.70 and len(amount_peers) >= 2:
            episode += sorted(amount_peers[:5], key=lambda row: row["ts"])
        if coordinated and corroborated_amount:
            episode += same_email[:8]
        episode = sorted({row["id"]: row for row in episode}.values(), key=lambda row: row["ts"])
        verdict = "fraud" if probability >= 0.85 and (report or coordinated or testing or region_novel) else "uncertain"
        if probability <= 0.15 and len(evidence) >= 2:
            verdict = "legitimate"
        suspected_episode = verdict == "fraud" or report or coordinated or probability >= 0.60
        affected = [row["id"] for row in episode] if suspected_episode and verdict != "legitimate" else []
        exposure = round(sum(abs(row["amount"]) for row in episode), 2) if affected else 0.0

        initial: list[Action] = []
        if report or probability >= 0.30 or coordinated:
            initial.append(make_action("CREATE_CASE", exposure, "R2/R6/R9 or section 3a: record the investigation."))
        if testing:
            initial.extend([
                make_action("DECLINE_TRANSACTION", exposure, "R5: testing sequence; L1 must authorize decline."),
                make_action("STEP_UP_AUTH", exposure, "R5: validate further activity."),
            ])
        if report:
            initial.append(make_action("BLOCK_CARD", exposure, "R2: customer explicitly disputed this transaction."))
        elif probability < 0.85:
            initial.append(make_action("VERIFY_WITH_CUSTOMER", exposure,
                                       "R1: graph signals remain inconclusive; ask the cardholder."))
        if coordinated and known_cards:
            initial.append(make_action("MONITOR_CONNECTED_CARDS", exposure,
                                       "R6/R9: monitor identified cards in the profile-linked customer groups."))
        if coordinated:
            initial.append(make_action("FILE_REPORT", exposure,
                                       "R6/R9: coordinated cross-customer pattern merits a report; L2 approval."))
            initial.append(make_action("ESCALATE_TO_ANALYST", exposure,
                                       "R9: analyst should review undocumented coordination."))
        elif report and exposure > 1000:
            initial.append(make_action("FILE_REPORT", exposure,
                                       "R2 and section 3a: customer denial and exposure above $1,000; L2 approval."))
        elif verdict == "uncertain" and seed["amount"] > 500:
            initial.append(make_action("ESCALATE_TO_ANALYST", exposure,
                                       "R8: uncertain high-value activity exceeds $500."))
        if not initial:
            initial.append(make_action("MONITOR_CARD", exposure, "R1: low evidence supports monitoring."))

        evidence_requests: list[EvidenceRequest] = []
        final = list(initial)
        what_changed = "nothing"
        if not report and any(a.action == "VERIFY_WITH_CUSTOMER" for a in initial):
            evidence_requests.append(EvidenceRequest(
                type="customer_validation", asked_after_step=len(self.last_trace),
                assumed_response="No customer reply received within 24 hours; this is a simulated benchmark assumption.",
            ))
            final = [a for a in initial if a.action != "VERIFY_WITH_CUSTOMER"]
            final.append(make_action("MONITOR_CARD", exposure,
                                     "R4: no customer reply within the simulated 24-hour window."))
            final.append(make_action("DECLINE_TRANSACTION", exposure,
                                     "R4: decline pending authorizations; L1 approval required."))
            what_changed = ("A simulated 24-hour nonresponse leaves identity uncertain; R4 replaces "
                            "verification with monitoring and a pending-authorization decline proposal.")
            evidence.append(EvidenceItem(
                claim="No customer reply was assumed after 24 hours for this benchmark scenario; this is not observed customer testimony.",
                source="external", ref="evidence_request:1:simulated_nonresponse", entity_ids=[seed["id"]],
            ))

        validate_actions(initial, exposure)
        validate_actions(final, exposure)
        file_report = any(a.action == "FILE_REPORT" for a in final)
        sar = self._sar(file_report, trigger, seed, episode, exposure, peer_customers, pattern, report)
        if verdict == "fraud":
            status = "closed_fraud" if not any(a.route != "auto" for a in final) else "open"
        elif verdict == "legitimate":
            status = "closed_legitimate"
        elif any(a.action == "ESCALATE_TO_ANALYST" for a in final):
            status = "escalated"
        else:
            status = "open"
        if verdict == "fraud":
            summary = (f"Transaction {seed['id']} shows {pattern.replace('_', ' ')} with "
                       f"{len(affected)} transaction(s) in the bounded episode. "
                       f"{'The customer report and transaction sequence' if report else 'The corroborated cross-customer motif'} supports a {probability:.0%} heuristic fraud assessment. "
                       "Any block or filing remains a human approval proposal.")
        else:
            summary = (f"Transaction {seed['id']} has {pattern.replace('_', ' ')} indicators, "
                       f"but the available evidence supports only a {probability:.0%} heuristic fraud assessment. "
                       "The cardholder's response and exact card-to-transaction mapping remain unresolved.")
        case = CasePart(
            status=status, verdict=verdict, fraud_probability=probability,
            pattern=pattern, pattern_description=description,
            affected_txn_ids=affected, first_suspicious_txn_id=affected[0] if affected else "",
            connected_card_ids=[row["card_id"] for row in known_cards] if coordinated else [],
            connected_device_profiles=[_profile(seed)] if peer_customers else [],
            exposure_usd=exposure, evidence=evidence,
            similar_prior_cases=[p["case_id"] for p in used_prior], summary=summary,
            written_to_graph=False, graph_case_id="",
        )
        confidence = min(0.96, 0.35 + 0.14 * int(report) + 0.12 * int(coordinated)
                         + 0.10 * int(len(amount_peers) >= 2) + 0.07 * int(seed["identity_status"] == "New")
                         + 0.06 * int(bool(used_prior)))
        self._trace("uncertainty_assessment", seed["id"],
                    f"risk_probability={probability:.3f}; evidence_confidence={confidence:.3f}; "
                    "both are uncalibrated heuristics")
        if verdict == "fraud" and probability >= 0.85:
            stop = "Strong independent evidence supports the current proposal; human approval gates high-impact actions."
        elif evidence_requests:
            stop = "R4's simulated nonresponse is recorded; a real customer answer or analyst decision is required."
        else:
            stop = "Further available graph expansion has low value; the case awaits customer or analyst clarification."
        return Answer(
            case_id=trigger["case_id"], case=case, evidence_requests=evidence_requests,
            next_best_actions=NextActions(initial=initial, final=final, what_changed=what_changed),
            sar=sar, stop_reason=stop, tool_calls=self.data.calls - call_start,
            tokens=0, latency_s=round(time.perf_counter() - started, 4),
        )

    def _trace(self, tool: str, seed: str, result: str) -> None:
        self.last_trace.append({"step": len(self.last_trace) + 1, "tool": tool,
                                "seed": seed, "result": result})

    @staticmethod
    def _sar(file_report: bool, trigger: dict, seed: dict, episode: list[dict],
             exposure: float, peer_customers: list[str], pattern: str,
             customer_report: bool) -> Sar:
        if not file_report:
            return Sar(file=False, reason="Section 3a: current evidence does not meet the report threshold.",
                       narrative="", subjects=[], total_amount_usd=0, activity_dates=[])
        dates = [row["ts"][:10] for row in episode]
        subjects = [seed["customer_id"], trigger["card_id"], *peer_customers[:5]]
        if customer_report and pattern != "undocumented":
            subjects = [seed["customer_id"], trigger["card_id"]]
            amounts = ", ".join(f"${row['amount']:.2f}" for row in episode)
            narrative = (
                f"Customer {seed['customer_id']} disputed transaction {seed['id']} on card {trigger['card_id']}. "
                f"The customer report states: {trigger['trigger_text']} "
                f"The flagged activity occurred on {seed['ts'][:10]} through the {seed['channel']} channel. "
                f"The bounded episode contains {len(episode)} transactions with amounts {amounts}. "
                f"The product code was {seed['product']} and billing region was {seed['addr1'] or 'not supplied'}. "
                f"The flagged transaction's device profile was {_profile(seed)}. "
                f"Its identity status was {seed['identity_status'] or 'not supplied'}. "
                f"The customer denial and transaction sequence support suspected {pattern.replace('_', ' ')}. "
                f"The identified exposure is ${exposure:.2f}; the supplied file does not provide merchant identity or a verified card key on each transaction. "
                "Under R2 and section 3a, the exposure threshold calls for a report subject to L2 approval."
            )
            reason = "R2 and section 3a: customer denial with exposure over $1,000; L2 approval pending."
        else:
            narrative = (
            f"Customer {seed['customer_id']} is associated with card {trigger['card_id']} in the case pack. "
            f"Transaction {seed['id']} occurred on {seed['ts'][:10]} for ${seed['amount']:.2f}. "
            f"The channel was {seed['channel']} and the product code was {seed['product']}. "
            f"The recorded billing region was {seed['addr1'] or 'not supplied'}. "
            f"The identity record described the device profile as {_profile(seed)}. "
            f"The same detailed profile appeared among {len(peer_customers)} other customer groups in the bounded search window. "
            f"The observed cross-customer motif is classified as {pattern.replace('_', ' ')}; a profile match alone does not establish a common physical device. "
            f"The identified suspicious episode totals ${exposure:.2f}. "
            "The supplied transaction file has no merchant identifier or verified card-to-transaction key, limiting attribution. "
            "Under R6 and R9, filing is recommended for human L2 review because the activity may be coordinated."
            )
            reason = "R6/R9 and section 3a: coordinated profile and amount motif; L2 approval pending."
        return Sar(file=True, reason=reason,
                   narrative=narrative, subjects=subjects, total_amount_usd=exposure,
                   activity_dates=[min(dates), max(dates)])
