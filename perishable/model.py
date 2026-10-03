"""Data model for the single-SKU single-store perishable replenishment problem."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class Batch:
    """A fixed (already purchased) inventory batch.

    Days are 0-based. The batch arrives at the start of ``arrival_day``
    (after the morning disposal step) and any remainder is disposed at the
    start of ``expiry_day``; it cannot be sold on its expiry day.
    """

    arrival_day: int
    expiry_day: int
    quantity: int


@dataclass(frozen=True)
class Scenario:
    """One demand scenario: a positive integer weight and H daily demands."""

    weight: int
    demand: tuple[int, ...]


@dataclass(frozen=True)
class Problem:
    """Full problem definition.

    - ``horizon``: number of selling days H (days 0..H-1); day H only runs
      the final disposal step.
    - ``batches``: fixed batches, identical across scenarios. On-hand
      inventory is represented as batches with ``arrival_day == 0``.
    - ``new_order_expiry``: expiry day of the new order (arrives day 0).
    - ``pack`` / ``moq`` / ``max_order``: q must be 0 or a multiple of
      ``pack`` that is >= ``moq`` and <= ``max_order``.
    - ``unit_cost`` / ``shortage_penalty`` / ``disposal_cost``: integer
      cents per unit (c, p, w).
    - ``scenarios``: demand scenarios with integer weights (not normalized).
    """

    horizon: int
    batches: tuple[Batch, ...]
    new_order_expiry: int
    pack: int
    moq: int
    max_order: int
    unit_cost: int
    shortage_penalty: int
    disposal_cost: int
    scenarios: tuple[Scenario, ...]


@dataclass(frozen=True)
class Evaluation:
    """Result of evaluating one order quantity q."""

    q: int
    purchase_cost: int
    expected_cost: Fraction
    service_ok: bool
    no_shortage_weight: int
    total_weight: int


@dataclass(frozen=True)
class OptimizeResult:
    """Result of optimize(): the cheapest feasible q and its evaluation."""

    feasible: bool
    q: int | None
    evaluation: Evaluation | None
