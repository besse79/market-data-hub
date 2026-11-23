from scripts.mkd_universe_gap_audit import classify


def test_distinguishes_identifiers_from_instruments():
    rows = [{"instrument_id": "a"}, {"instrument_id": "a"}, {"instrument_id": "b"}]
    result = classify(4, 3, rows)
    assert result["instruments_with_active_yahoo"] == 2
    assert result["instruments_without_active_yahoo"] == 2
    assert result["instruments_with_multiple_active_yahoo"] == 1
    assert not result["collection_universe_complete"]
    assert not result["paper_authorized"]


def test_complete_mapping_still_does_not_authorize_paper():
    result = classify(2, 2, [{"instrument_id": "a"}, {"instrument_id": "b"}])
    assert result["collection_universe_complete"]
    assert not result["paper_authorized"]
