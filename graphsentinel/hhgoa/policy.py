"""Deterministic approval routes and the high impact rule R10."""

from graphsentinel.hhgoa.contracts import Action, ActionName


AUTO = {
    "ALLOW_TRANSACTION", "MONITOR_CARD", "MONITOR_CONNECTED_CARDS",
    "WARN_CUSTOMER", "VERIFY_WITH_CUSTOMER", "STEP_UP_AUTH",
    "GENERATE_REPORT", "CREATE_CASE", "ESCALATE_TO_ANALYST",
    "CLOSE_NO_FRAUD",
}


def route_for(action: ActionName, exposure_usd: float) -> str:
    if action in AUTO:
        return "auto"
    if action == "DECLINE_TRANSACTION":
        return "L1"
    if action == "BLOCK_CARD":
        return "L2" if exposure_usd > 2500 else "L1"
    if action in {"BLOCK_ALL_CARDS", "FILE_REPORT"}:
        return "L2"
    raise ValueError(f"Unknown action: {action}")


def make_action(action: ActionName, exposure_usd: float, reason: str) -> Action:
    return Action(action=action, route=route_for(action, exposure_usd), reason=reason)


def validate_actions(actions: list[Action], exposure_usd: float,
                     confirmed_cards: int = 0, credentials_compromised: bool = False) -> None:
    for item in actions:
        if item.route != route_for(item.action, exposure_usd):
            raise ValueError(f"Incorrect route for {item.action}")
        if item.action == "BLOCK_ALL_CARDS" and confirmed_cards < 2 and not credentials_compromised:
            raise ValueError("R10 forbids blocking all cards without proof of a wider compromise")
