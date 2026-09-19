from graphsentinel.hhgoa.tigergraph import GraphPayload, device_profile_id


def test_transaction_payload_uses_only_observed_relationships():
    tx = {
        "id": "3514030", "customer_id": "C12382", "ts": "2016-12-04 19:55:28",
        "amount": 77.07, "product": "W", "channel": "in_person", "risk": 0.61,
        "card1": "21139", "card2": "242.0", "card3": "150.0", "card4": "visa",
        "card5": "166.0", "card6": "debit", "addr1": "444.0", "addr2": "87.0",
        "email": None, "recipient_email": None,
    }
    payload = GraphPayload()
    payload.add_transaction(tx)
    body = payload.body()
    assert "3514030" in body["vertices"]["Transaction"]
    assert "C12382" in body["vertices"]["Customer"]
    assert "MADE" in body["edges"]["Customer"]["C12382"]
    assert "CARD_TX" not in str(body)
    assert "Merchant" not in str(body)


def test_identity_profile_is_stable_and_case_anchor_is_explicit():
    row = {"id": "3514030", "device_info": "Windows", "os": "Windows 10",
           "browser": "edge 16.0", "screen": "1366x768", "identity_status": "New",
           "proxy_status": None}
    assert device_profile_id(row) == device_profile_id(dict(row))
    payload = GraphPayload()
    payload.add_identity(row)
    assert device_profile_id(row) in payload.body()["vertices"]["DeviceProfile"]
    payload.add_anchor({"case_id": "HHG-001", "customer_id": "C12382",
                        "card_id": "C12382-K1", "flagged_txn_id": "3514030"})
    assert "CARD_TX" in payload.body()["edges"]["Card"]["C12382-K1"]
