"""Cross-check against an independent brute-force reference implementation.

The reference below is deliberately written as a separate, straightforward
simulation so that the randomized tests validate the library's FIFO
simulation, exact arithmetic, legality rules, and optimization end to end.
"""

from __future__ import annotations

import random
from fractions import Fraction

from perishable import Batch, Problem, Scenario, evaluate, is_legal_quantity, optimize


def reference_simulate(problem: Problem, demand: tuple[int, ...], q: int) -> tuple[int, int]:
    """Independent simulation; returns (shortage_units, disposed_units)."""
    lots = []  # [expiry_day, quantity], kept in arrival order
    for batch in problem.batches:
        if batch.arrival_day == 0:
            lots.append([batch.expiry_day, batch.quantity])
    if q > 0:
        lots.append([problem.new_order_expiry, q])
    shortage = 0
    disposed = 0
    for day in range(problem.horizon + 1):
        for lot in lots:
            if lot[0] == day:
                disposed += lot[1]
        lots = [lot for lot in lots if lot[0] != day]
        if day == problem.horizon:
            break
        if day > 0:
            for batch in problem.batches:
                if batch.arrival_day == day:
                    lots.append([batch.expiry_day, batch.quantity])
        need = demand[day]
        for lot in lots:
            take = min(lot[1], need)
            lot[1] -= take
            need -= take
            if need == 0:
                break
        lots = [lot for lot in lots if lot[1] > 0]
        shortage += need
    return shortage, disposed


def reference_evaluate(problem: Problem, q: int) -> tuple[Fraction, bool]:
    total_weight = 0
    good_weight = 0
    weighted_cost = 0
    for scenario in problem.scenarios:
        shortage, disposed = reference_simulate(problem, scenario.demand, q)
        weighted_cost += scenario.weight * (
            problem.shortage_penalty * shortage + problem.disposal_cost * disposed
        )
        total_weight += scenario.weight
        if shortage == 0:
            good_weight += scenario.weight
    cost = Fraction(problem.unit_cost * q) + Fraction(weighted_cost, total_weight)
    service_ok = Fraction(good_weight, total_weight) >= Fraction(95, 100)
    return cost, service_ok


def reference_legal_q(problem: Problem, q: int) -> bool:
    if q == 0:
        return True
    return (
        q > 0
        and q % problem.pack == 0
        and q >= problem.moq
        and q <= problem.max_order
    )


def reference_optimize(problem: Problem) -> tuple[int, Fraction] | None:
    best = None
    for q in range(0, problem.max_order + 1):
        if not reference_legal_q(problem, q):
            continue
        cost, service_ok = reference_evaluate(problem, q)
        if not service_ok:
            continue
        if best is None or cost < best[1]:
            best = (q, cost)
    return best


def random_problem(rng: random.Random) -> Problem:
    horizon = rng.randint(1, 4)
    batches = []
    for _ in range(rng.randint(0, 4)):
        arrival = rng.randint(0, horizon - 1)
        expiry = rng.randint(arrival + 1, horizon)
        batches.append(
            Batch(
                arrival_day=arrival,
                expiry_day=expiry,
                quantity=rng.randint(1, 5),
            )
        )
    scenarios = []
    for _ in range(rng.randint(1, 3)):
        scenarios.append(
            Scenario(
                weight=rng.randint(1, 20),
                demand=tuple(rng.randint(0, 5) for _ in range(horizon)),
            )
        )
    pack = rng.randint(1, 3)
    moq = rng.randint(0, 6)
    max_order = rng.randint(0, 15)
    return Problem(
        horizon=horizon,
        batches=tuple(batches),
        new_order_expiry=rng.randint(1, horizon),
        pack=pack,
        moq=moq,
        max_order=max_order,
        unit_cost=rng.randint(0, 10),
        shortage_penalty=rng.randint(0, 20),
        disposal_cost=rng.randint(0, 10),
        scenarios=tuple(scenarios),
    )


def test_random_instances_match_reference():
    rng = random.Random(20261004)
    infeasible_count = 0
    checked = 0
    for _ in range(400):
        problem = random_problem(rng)
        for q in range(0, problem.max_order + 2):
            assert is_legal_quantity(problem, q) == reference_legal_q(problem, q)
            if not reference_legal_q(problem, q):
                continue
            expected_cost, service_ok = reference_evaluate(problem, q)
            evaluation = evaluate(problem, q)
            assert evaluation.expected_cost == expected_cost
            assert evaluation.service_ok == service_ok
            checked += 1
        reference_best = reference_optimize(problem)
        result = optimize(problem)
        if reference_best is None:
            infeasible_count += 1
            assert not result.feasible
        else:
            assert result.feasible
            assert result.q == reference_best[0]
            assert result.evaluation.expected_cost == reference_best[1]
    assert checked > 0
    # The random suite must actually exercise the all-infeasible path.
    assert infeasible_count > 0
