"""Evaluation of a fixed order quantity via exact scenario simulation."""

from __future__ import annotations

from collections import deque
from fractions import Fraction

from .model import Batch, Evaluation, Problem, Scenario


def _validate_problem(problem: Problem) -> None:
    if problem.horizon < 1:
        raise ValueError("horizon must be >= 1")
    if problem.pack < 1:
        raise ValueError("pack must be >= 1")
    if problem.moq < 0:
        raise ValueError("moq must be >= 0")
    if problem.max_order < 0:
        raise ValueError("max_order must be >= 0")
    if not (0 < problem.new_order_expiry <= problem.horizon):
        raise ValueError("new_order_expiry must be in 1..horizon")
    for name, value in (
        ("unit_cost", problem.unit_cost),
        ("shortage_penalty", problem.shortage_penalty),
        ("disposal_cost", problem.disposal_cost),
    ):
        if value < 0:
            raise ValueError(f"{name} must be >= 0")
    if not problem.scenarios:
        raise ValueError("at least one scenario is required")
    for batch in problem.batches:
        if not (0 <= batch.arrival_day < batch.expiry_day <= problem.horizon):
            raise ValueError("batch must satisfy 0 <= arrival_day < expiry_day <= horizon")
        if batch.quantity <= 0:
            raise ValueError("batch quantity must be positive")
    for scenario in problem.scenarios:
        if scenario.weight <= 0:
            raise ValueError("scenario weight must be positive")
        if len(scenario.demand) != problem.horizon:
            raise ValueError("scenario demand must have exactly horizon entries")
        if any(d < 0 for d in scenario.demand):
            raise ValueError("scenario demand must be non-negative")


def is_legal_quantity(problem: Problem, q: int) -> bool:
    """Return True if q is 0 or a pack multiple in [moq, max_order]."""
    if isinstance(q, bool) or not isinstance(q, int):
        return False
    if q == 0:
        return True
    return q >= problem.moq and q <= problem.max_order and q % problem.pack == 0


def _simulate_scenario(problem: Problem, scenario: Scenario, q: int) -> tuple[int, int]:
    """Simulate one scenario; return (shortage_units, disposed_units)."""
    horizon = problem.horizon
    arrivals: dict[int, list[Batch]] = {}
    for batch in problem.batches:
        arrivals.setdefault(batch.arrival_day, []).append(batch)

    # FIFO queue of [expiry_day, quantity], in arrival order. Day-0 fixed
    # batches keep input order; the new order is queued behind all of them.
    inventory: deque[list[int]] = deque()
    for batch in arrivals.get(0, []):
        inventory.append([batch.expiry_day, batch.quantity])
    if q > 0:
        inventory.append([problem.new_order_expiry, q])

    shortage = 0
    disposed = 0
    for day in range(horizon + 1):
        # 1) Morning disposal of batches reaching their expiry day.
        kept: deque[list[int]] = deque()
        for expiry, qty in inventory:
            if expiry == day:
                disposed += qty
            else:
                kept.append([expiry, qty])
        inventory = kept
        if day == horizon:
            break  # Day H runs only the final disposal.
        # 2) Receive today's arrivals (day-0 arrivals were seeded above).
        if day > 0:
            for batch in arrivals.get(day, []):
                inventory.append([batch.expiry_day, batch.quantity])
        # 3) Serve demand, strict FIFO by arrival order.
        remaining = scenario.demand[day]
        while remaining > 0 and inventory:
            head = inventory[0]
            take = min(head[1], remaining)
            head[1] -= take
            remaining -= take
            if head[1] == 0:
                inventory.popleft()
        shortage += remaining  # Unmet demand is lost, not backlogged.
    return shortage, disposed


def evaluate(problem: Problem, q: int) -> Evaluation:
    """Evaluate expected cost (Fraction, in cents) and service feasibility."""
    _validate_problem(problem)
    if not is_legal_quantity(problem, q):
        raise ValueError(
            f"illegal order quantity {q}: must be 0 or a multiple of pack "
            f"in [moq, max_order]"
        )

    total_weight = 0
    no_shortage_weight = 0
    weighted_cost = 0  # Exact integer: sum of weight * scenario cost (cents).
    for scenario in problem.scenarios:
        shortage, disposed = _simulate_scenario(problem, scenario, q)
        scenario_cost = (
            problem.shortage_penalty * shortage + problem.disposal_cost * disposed
        )
        weighted_cost += scenario.weight * scenario_cost
        total_weight += scenario.weight
        if shortage == 0:
            no_shortage_weight += scenario.weight

    expected_cost = Fraction(problem.unit_cost * q) + Fraction(
        weighted_cost, total_weight
    )
    # Exact 95% service check: good / total >= 95/100  <=>  20*good >= 19*total.
    service_ok = 20 * no_shortage_weight >= 19 * total_weight
    return Evaluation(
        q=q,
        purchase_cost=problem.unit_cost * q,
        expected_cost=expected_cost,
        service_ok=service_ok,
        no_shortage_weight=no_shortage_weight,
        total_weight=total_weight,
    )
