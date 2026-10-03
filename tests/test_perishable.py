"""Automated tests for the perishable replenishment library."""

from __future__ import annotations

from fractions import Fraction

import pytest

from perishable import (
    Batch,
    Problem,
    Scenario,
    evaluate,
    is_legal_quantity,
    optimize,
)


def make_nonconvex_problem() -> Problem:
    """The non-convex counterexample from the specification."""
    return Problem(
        horizon=3,
        batches=(Batch(arrival_day=1, expiry_day=2, quantity=1),),
        new_order_expiry=3,
        pack=1,
        moq=1,
        max_order=10,
        unit_cost=1,
        shortage_penalty=100,
        disposal_cost=1,
        scenarios=(
            Scenario(weight=95, demand=(0, 0, 0)),
            Scenario(weight=5, demand=(1, 1, 1)),
        ),
    )


class TestNonConvexCounterexample:
    def test_local_minimum_at_q1(self):
        problem = make_nonconvex_problem()
        costs = {q: evaluate(problem, q).expected_cost for q in range(0, 5)}
        assert costs[0] == Fraction(219, 20)  # 10.95
        assert costs[1] == Fraction(79, 10)  # 7.90, local minimum
        assert costs[2] == Fraction(99, 10)  # 9.90
        assert costs[3] == Fraction(137, 20)  # 6.85, global minimum
        assert costs[1] < costs[0] and costs[1] < costs[2]

    def test_global_optimum_is_q3(self):
        result = optimize(make_nonconvex_problem())
        assert result.feasible
        assert result.q == 3
        assert result.evaluation.expected_cost == Fraction(137, 20)
        assert float(result.evaluation.expected_cost) == 6.85
        assert result.evaluation.service_ok


class TestQuantityLegality:
    def test_pack_moq_cap_rules(self):
        problem = Problem(
            horizon=1,
            batches=(),
            new_order_expiry=1,
            pack=4,
            moq=6,
            max_order=20,
            unit_cost=1,
            shortage_penalty=1,
            disposal_cost=1,
            scenarios=(Scenario(weight=1, demand=(0,)),),
        )
        assert is_legal_quantity(problem, 0)
        assert not is_legal_quantity(problem, 4)  # below MOQ
        assert is_legal_quantity(problem, 8)  # smallest pack multiple >= MOQ
        assert not is_legal_quantity(problem, 9)  # not a pack multiple
        assert is_legal_quantity(problem, 20)
        assert not is_legal_quantity(problem, 24)  # above cap
        assert not is_legal_quantity(problem, -4)

    def test_evaluate_rejects_illegal_q(self):
        problem = make_nonconvex_problem()
        with pytest.raises(ValueError):
            evaluate(problem, -1)

    def test_optimize_skips_illegal_candidates(self):
        # Only q in {0, 8, 12, 16, 20} may be considered; demand 9 forces q=12.
        problem = Problem(
            horizon=1,
            batches=(),
            new_order_expiry=1,
            pack=4,
            moq=6,
            max_order=20,
            unit_cost=1,
            shortage_penalty=1000,
            disposal_cost=0,
            scenarios=(Scenario(weight=1, demand=(9,)),),
        )
        result = optimize(problem)
        assert result.feasible
        assert result.q == 12


class TestFifoAndExpiry:
    def base_kwargs(self, **overrides):
        kwargs = dict(
            horizon=2,
            batches=(),
            new_order_expiry=2,
            pack=1,
            moq=1,
            max_order=10,
            unit_cost=0,
            shortage_penalty=100,
            disposal_cost=5,
            scenarios=(Scenario(weight=1, demand=(0, 0)),),
        )
        kwargs.update(overrides)
        return kwargs

    def test_new_order_sold_after_day0_fixed_batches(self):
        # Day-0 fixed batch (expires day 1) must be consumed before the new
        # order; otherwise it would be disposed on day 1 and cost w.
        problem = Problem(
            **self.base_kwargs(
                batches=(Batch(arrival_day=0, expiry_day=1, quantity=1),),
                scenarios=(Scenario(weight=1, demand=(1, 1)),),
            )
        )
        evaluation = evaluate(problem, 1)
        assert evaluation.expected_cost == 0  # nothing disposed, no shortage

    def test_same_day_fixed_batches_follow_input_order(self):
        # B1 expires day 1, B2 expires day 2. Selling B1 first (input order)
        # avoids disposal; any other order would dispose B1 on day 1.
        problem = Problem(
            **self.base_kwargs(
                batches=(
                    Batch(arrival_day=0, expiry_day=1, quantity=1),
                    Batch(arrival_day=0, expiry_day=2, quantity=1),
                ),
                scenarios=(Scenario(weight=1, demand=(1, 1)),),
            )
        )
        assert evaluate(problem, 0).expected_cost == 0

    def test_cross_day_fifo_consumption(self):
        # Day-0 leftover must be sold on day 1 before the day-1 arrival.
        problem = Problem(
            **self.base_kwargs(
                batches=(
                    Batch(arrival_day=0, expiry_day=2, quantity=3),
                    Batch(arrival_day=1, expiry_day=2, quantity=2),
                ),
                scenarios=(Scenario(weight=1, demand=(2, 1)),),
            )
        )
        # Day 0: sell 2 of batch 1. Day 1: sell batch 1's last unit (FIFO
        # ahead of the day-1 arrival); batch 2 (2 units) disposed on day 2.
        assert evaluate(problem, 0).expected_cost == 2 * 5

    def test_batch_cannot_be_sold_on_expiry_day(self):
        problem = Problem(
            **self.base_kwargs(
                batches=(Batch(arrival_day=0, expiry_day=1, quantity=1),),
                scenarios=(Scenario(weight=1, demand=(0, 5)),),
            )
        )
        # The unit is disposed on day 1 before demand is served.
        assert evaluate(problem, 0).expected_cost == 5 * 100 + 1 * 5

    def test_new_order_cannot_be_sold_on_expiry_day(self):
        problem = Problem(
            **self.base_kwargs(
                new_order_expiry=1,
                scenarios=(Scenario(weight=1, demand=(0, 2)),),
            )
        )
        evaluation = evaluate(problem, 2)
        assert evaluation.expected_cost == 2 * 100 + 2 * 5

    def test_day_h_runs_only_final_disposal(self):
        # Batch expires exactly at H: sellable through day H-1, disposed day H.
        problem = Problem(
            **self.base_kwargs(
                batches=(Batch(arrival_day=1, expiry_day=2, quantity=2),),
                scenarios=(Scenario(weight=1, demand=(0, 1)),),
            )
        )
        assert evaluate(problem, 0).expected_cost == 1 * 5

    def test_unmet_demand_is_not_backlogged(self):
        problem = Problem(
            **self.base_kwargs(
                batches=(Batch(arrival_day=1, expiry_day=2, quantity=1),),
                scenarios=(Scenario(weight=1, demand=(3, 3)),),
            )
        )
        # Day 0: shortage 3 (lost). Day 1: arrival covers 1, shortage 2.
        assert evaluate(problem, 0).expected_cost == 5 * 100


def service_problem(good_weight: int, bad_weight: int) -> Problem:
    """q=0: first scenario has no shortage, second always shortfalls."""
    return Problem(
        horizon=1,
        batches=(),
        new_order_expiry=1,
        pack=1,
        moq=1,
        max_order=10,
        unit_cost=0,
        shortage_penalty=100,
        disposal_cost=0,
        scenarios=(
            Scenario(weight=good_weight, demand=(0,)),
            Scenario(weight=bad_weight, demand=(1,)),
        ),
    )


class TestServiceLevel:
    def test_exact_95_percent_boundary_passes(self):
        evaluation = evaluate(service_problem(95, 5), 0)
        assert evaluation.service_ok
        assert evaluation.no_shortage_weight == 95
        assert evaluation.total_weight == 100

    def test_just_below_95_percent_fails(self):
        assert not evaluate(service_problem(94, 6), 0).service_ok

    def test_boundary_with_large_weights_is_exact(self):
        # 0.95 is not exactly representable in binary floating point; the
        # check must stay exact for huge weights.
        scale = 10**15
        assert evaluate(service_problem(95 * scale, 5 * scale), 0).service_ok
        assert not evaluate(
            service_problem(95 * scale - 1, 5 * scale + 1), 0
        ).service_ok

    def test_weights_need_not_be_normalized(self):
        evaluation = evaluate(service_problem(190, 10), 0)
        assert evaluation.service_ok


class TestOptimizeBehavior:
    def test_tie_breaks_to_smaller_q(self):
        # All positive q have identical cost 0; the smallest must win.
        problem = Problem(
            horizon=1,
            batches=(),
            new_order_expiry=1,
            pack=2,
            moq=2,
            max_order=6,
            unit_cost=0,
            shortage_penalty=100,
            disposal_cost=0,
            scenarios=(Scenario(weight=1, demand=(1,)),),
        )
        result = optimize(problem)
        assert result.feasible
        assert result.q == 2

    def test_infeasible_when_no_q_meets_service_target(self):
        # Cap Q=4 can never cover demand 5; every scenario shortfalls.
        problem = Problem(
            horizon=1,
            batches=(),
            new_order_expiry=1,
            pack=1,
            moq=1,
            max_order=4,
            unit_cost=1,
            shortage_penalty=100,
            disposal_cost=0,
            scenarios=(Scenario(weight=1, demand=(5,)),),
        )
        result = optimize(problem)
        assert not result.feasible
        assert result.q is None
        assert result.evaluation is None

    def test_q_zero_is_a_valid_candidate(self):
        problem = Problem(
            horizon=1,
            batches=(),
            new_order_expiry=1,
            pack=1,
            moq=1,
            max_order=10,
            unit_cost=1,
            shortage_penalty=100,
            disposal_cost=1,
            scenarios=(Scenario(weight=1, demand=(0,)),),
        )
        result = optimize(problem)
        assert result.feasible
        assert result.q == 0
        assert result.evaluation.expected_cost == 0

    def test_float_trap_prefers_truly_cheaper_q(self):
        # cost(q=1) == 1 exactly; cost(q=2) == 1 - 1/(10**18 + 1), which
        # rounds to 1.0 in float64. Exact arithmetic must pick q=2.
        big = 10**18
        problem = Problem(
            horizon=1,
            batches=(),
            new_order_expiry=1,
            pack=1,
            moq=1,
            max_order=2,
            unit_cost=0,
            shortage_penalty=1,
            disposal_cost=0,
            scenarios=(
                Scenario(weight=big, demand=(1,)),
                Scenario(weight=1, demand=(big + 2,)),
            ),
        )
        cost1 = evaluate(problem, 1).expected_cost
        cost2 = evaluate(problem, 2).expected_cost
        assert cost1 == 1
        assert cost2 == Fraction(big, big + 1)
        assert float(cost1) == float(cost2)  # the trap is real
        assert cost2 < cost1
        result = optimize(problem)
        assert result.feasible
        assert result.q == 2
