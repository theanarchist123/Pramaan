import pytest

from app.core import merkle as m

LEAVES = {n: [m.leaf_hash(f"entry-{i}".encode()) for i in range(n)] for n in range(1, 20)}


@pytest.mark.parametrize("n", range(1, 20))
def test_every_leaf_of_every_size_has_a_valid_inclusion_proof(n):
    leaves, r = LEAVES[n], m.root(LEAVES[n])
    for i in range(n):
        assert m.verify_inclusion(leaves[i], i, n, m.inclusion_proof(leaves, i), r)


def test_a_wrong_leaf_index_or_root_fails_inclusion():
    leaves, r = LEAVES[11], m.root(LEAVES[11])
    p = m.inclusion_proof(leaves, 4)
    assert not m.verify_inclusion(m.leaf_hash(b"forged"), 4, 11, p, r)
    assert not m.verify_inclusion(leaves[4], 5, 11, p, r)
    assert not m.verify_inclusion(leaves[4], 4, 11, p, m.root(LEAVES[12]))


def test_every_older_tree_is_provably_a_prefix_of_every_newer_one():
    for second in range(1, 20):
        for first in range(1, second + 1):
            proof = m.consistency_proof(LEAVES[second], first)
            assert m.verify_consistency(first, second, m.root(LEAVES[first]), m.root(LEAVES[second]), proof), (first, second)


def test_rewriting_history_breaks_consistency():
    # The log of 12 whose entry 3 was quietly rewritten is NOT consistent with the earlier published root of 8.
    honest = LEAVES[12]
    rewritten = honest[:3] + [m.leaf_hash(b"rewritten")] + honest[4:]
    proof = m.consistency_proof(rewritten, 8)
    assert not m.verify_consistency(8, 12, m.root(LEAVES[8]), m.root(rewritten), proof)


def test_empty_tree_and_bad_ranges():
    assert m.root([]) == m._h(b"")
    with pytest.raises(IndexError):
        m.inclusion_proof(LEAVES[3], 3)
    assert not m.verify_consistency(0, 3, b"", b"", [])


def test_checkpoint_text_is_fixed_and_proofs_round_trip_through_hex():
    from app.api.verify import checkpoint_text

    assert checkpoint_text(3, "ab") == "pramaan-log-checkpoint-v1\nsize=3\nroot=ab\n"
    leaves, r = LEAVES[7], m.root(LEAVES[7])
    wire = [p.hex() for p in m.inclusion_proof(leaves, 2)]
    assert m.verify_inclusion(leaves[2], 2, 7, [bytes.fromhex(x) for x in wire], r)
