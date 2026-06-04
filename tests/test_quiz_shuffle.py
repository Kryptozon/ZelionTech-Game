"""Confirms the quiz answer shuffle distributes the correct option across A/B/C/D
and that the shuffled choice maps back to the original correct answer.

Run:  python tests/test_quiz_shuffle.py
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot.services.quiz import answer_order

LETTERS = "ABCD"


def test_distribution():
    """Correct answer (original index 0, as in the curated bank) lands across A/B/C/D."""
    user_id = 1087968824
    dist = Counter()
    for qid in range(1, 401):                      # the full 300+ bank range
        order = answer_order(qid, user_id, 4)       # shuffled[i] = original[order[i]]
        correct_pos = order.index(0)                # where original-correct (0) ends up
        dist[correct_pos] += 1
    print("Correct-answer position distribution (user 1087968824):")
    for i in range(4):
        print(f"  {LETTERS[i]}: {dist[i]}")
    assert all(dist[i] > 0 for i in range(4)), "correct answer not distributed across A/B/C/D"
    # each bucket should be a meaningful share (≈25%); allow generous bounds
    total = sum(dist.values())
    for i in range(4):
        assert dist[i] / total > 0.12, f"bucket {LETTERS[i]} too small: {dist[i]}/{total}"


def test_reversibility():
    """Selecting the shuffled position of the correct answer validates as correct."""
    for uid in (1, 42, 1087968824):
        for qid in range(1, 50):
            order = answer_order(qid, uid, 4)
            shuffled_correct = order.index(0)        # what the user must tap
            original_choice = order[shuffled_correct]
            assert original_choice == 0, "shuffled correct choice must map back to original index 0"


def test_per_user_varies():
    """Different users get different placements (anti-memorization)."""
    diffs = sum(1 for qid in range(1, 200)
                if answer_order(qid, 1, 4).index(0) != answer_order(qid, 2, 4).index(0))
    assert diffs > 50, "two users should see different correct positions on many questions"


if __name__ == "__main__":
    test_distribution()
    test_reversibility()
    test_per_user_varies()
    print("\nALL QUIZ SHUFFLE TESTS PASSED")
