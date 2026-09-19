from graphsentinel.hhgoa.engine import BenchmarkInvestigator


class TinyTestingSequence:
    source = "external"
    reference_prefix = "index"

    def __init__(self):
        self.calls = 0
        self.seed = {
            "id": "1004", "customer_id": "C00001", "ts": "2016-11-01 10:30:00",
            "amount": 250.0, "product": "C", "channel": "online", "risk": .2,
            "addr1": None, "addr2": None, "email": "example.com",
            "recipient_email": None, "identity_status": None, "proxy_status": None,
            "device_info": None, "os": None, "browser": None, "screen": None,
        }

    def transaction(self, _id):
        self.calls += 1
        return self.seed

    def history_stats(self, *_args):
        self.calls += 1
        return {"count": 8, "median_amount": 25.0, "region_count": 0, "distinct_regions": 0}

    def customer_window(self, *_args, **_kwargs):
        self.calls += 1
        return [self.seed, *[
            {**self.seed, "id": str(1000 + index), "amount": amount,
             "ts": f"2016-11-01 10:{index * 5:02d}:00"}
            for index, amount in enumerate((1.0, 2.5, 3.0), start=1)
        ]]

    def profile_peers(self, *_args):
        return []

    def prior_cases(self, *_args):
        self.calls += 1
        return []

    def known_cards(self, *_args):
        return []


def test_testing_motif_recommends_decline_and_step_up_without_auto_execution():
    data = TinyTestingSequence()
    trigger = {"case_id": "HHG-999", "flagged_txn_id": "1004",
               "customer_id": "C00001", "card_id": "C00001-K1",
               "trigger_type": "risk_score", "trigger_text": "Alert",
               "opened_at": "2016-11-01 10:31:00"}
    answer = BenchmarkInvestigator(data).investigate(trigger)
    assert answer.case.pattern == "card_testing"
    actions = {item.action: item.route for item in answer.next_best_actions.initial}
    assert actions["DECLINE_TRANSACTION"] == "L1"
    assert actions["STEP_UP_AUTH"] == "auto"
    assert answer.case.written_to_graph is False
