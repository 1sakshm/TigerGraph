from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDecision:
    reference: str
    approval_required: bool
    allowed: bool


class PolicyEngine:
    """Local safety baseline; dataset policy can only make this more restrictive."""

    RULES = {
        "REQUEST_CUSTOMER_CONFIRMATION": PolicyDecision("GS-POL-01", False, True),
        "REQUEST_STEP_UP_AUTHENTICATION": PolicyDecision("GS-POL-01", False, True),
        "MONITOR_ACCOUNT": PolicyDecision("GS-POL-02", False, True),
        "ESCALATE_ANALYST": PolicyDecision("GS-POL-03", False, True),
        "BLOCK_CARD": PolicyDecision("GS-POL-04", True, True),
        "BLOCK_ACCOUNT": PolicyDecision("GS-POL-04", True, True),
        "FILE_REPORT": PolicyDecision("GS-POL-05", True, True),
    }

    def evaluate(self, action: str) -> PolicyDecision:
        return self.RULES.get(action, PolicyDecision("GS-POL-DENY", True, False))

    def execute(self, action: str, approved_by: str | None = None) -> str:
        decision = self.evaluate(action)
        if not decision.allowed:
            raise PermissionError(f"Action {action} is not permitted")
        if decision.approval_required and not approved_by:
            raise PermissionError(f"Action {action} requires analyst approval")
        return action
