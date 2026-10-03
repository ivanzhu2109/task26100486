"""Global optimization over the finite set of legal order quantities."""

from __future__ import annotations

from .evaluate import evaluate
from .model import OptimizeResult, Problem


def _legal_quantities(problem: Problem) -> list[int]:
    """All legal q in ascending order: 0 plus pack multiples in [moq, Q]."""
    quantities = [0]
    if problem.pack >= 1 and problem.max_order >= 1:
        first = max(problem.moq, problem.pack)
        # Smallest multiple of pack that is >= first.
        first = ((first + problem.pack - 1) // problem.pack) * problem.pack
        quantities.extend(range(first, problem.max_order + 1, problem.pack))
    return quantities


def optimize(problem: Problem) -> OptimizeResult:
    """Return the cheapest service-feasible q (ties -> smaller q)."""
    best = None
    for q in _legal_quantities(problem):
        evaluation = evaluate(problem, q)
        if not evaluation.service_ok:
            continue
        # Ascending q with a strict "<" keeps the smaller q on exact ties.
        if best is None or evaluation.expected_cost < best.expected_cost:
            best = evaluation
    if best is None:
        return OptimizeResult(feasible=False, q=None, evaluation=None)
    return OptimizeResult(feasible=True, q=best.q, evaluation=best)
