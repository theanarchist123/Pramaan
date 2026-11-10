"""Tests for members_by_state plugin pure functions."""
from plugins.members_by_state import aggregate_state_counts, summarize_state_data


def test_aggregate_state_counts():
    raw_data = [("CA", 10), ("NY", 15), (None, 2), ("", 1), ("TX", 5)]
    res = aggregate_state_counts(raw_data)
    assert len(res) == 4
    assert res[0] == {"state": "NY", "count": 15}
    assert res[1] == {"state": "CA", "count": 10}
    assert res[2] == {"state": "TX", "count": 5}
    assert res[3] == {"state": "Unknown", "count": 3}


def test_summarize_state_data():
    items = [
        {"state": "NY", "count": 15},
        {"state": "CA", "count": 10},
        {"state": "Unknown", "count": 3},
    ]
    summary = summarize_state_data(items)
    assert summary["total_approved_members"] == 28
    assert summary["total_states"] == 2
    assert summary["items"] == items


def test_empty_state_data():
    items = aggregate_state_counts([])
    assert items == []
    summary = summarize_state_data(items)
    assert summary["total_approved_members"] == 0
    assert summary["total_states"] == 0
