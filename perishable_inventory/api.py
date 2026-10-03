"""对外接口：evaluate 与 optimize。

费用全程用整数分与 fractions.Fraction 精确计算，不用浮点；
95% 服务水平边界用整数交叉相乘判断，避免舍入误差。
"""
from __future__ import annotations

from fractions import Fraction

from .models import Evaluation, OptimizeResult, Problem
from .simulate import simulate_scenario

# 服务水平门槛：无缺货场景权重之和至少占总权重的 95%（即 19/20）。
_SERVICE_NUM = 19
_SERVICE_DEN = 20


def valid_quantities(problem: Problem) -> list[int]:
    """全部合法订单量：0，或满足 MOQ 的 pack 整数倍且不超过 Q。"""
    quantities = [0]
    if problem.pack > 0:
        first = -(-problem.moq // problem.pack)  # ceil(moq / pack)
        for k in range(first, problem.max_qty // problem.pack + 1):
            quantities.append(k * problem.pack)
    return quantities


def _check_quantity(problem: Problem, q: int) -> None:
    if q == 0:
        return
    if q % problem.pack != 0:
        raise ValueError(f"q={q} 不是包装量 pack={problem.pack} 的整数倍")
    if q < problem.moq:
        raise ValueError(f"q={q} 低于最小起订量 MOQ={problem.moq}")
    if q > problem.max_qty:
        raise ValueError(f"q={q} 超过采购上限 Q={problem.max_qty}")


def evaluate(problem: Problem, q: int) -> Evaluation:
    """评估给定订单量的期望费用及服务水平是否达标。"""
    _check_quantity(problem, q)
    total_weight = sum(s.weight for s in problem.scenarios)
    if total_weight <= 0:
        raise ValueError("场景权重之和必须为正")

    shortage_cost_sum = 0  # sum(weight * 缺货件数) * p
    waste_cost_sum = 0     # sum(weight * 报废件数) * w
    service_weight = 0
    for scenario in problem.scenarios:
        shortage, waste = simulate_scenario(problem, scenario, q)
        shortage_cost_sum += scenario.weight * shortage * problem.shortage_penalty
        waste_cost_sum += scenario.weight * waste * problem.waste_cost
        if shortage == 0:
            service_weight += scenario.weight

    purchase_cost = problem.cost_per_unit * q
    expected_shortage = Fraction(shortage_cost_sum, total_weight)
    expected_waste = Fraction(waste_cost_sum, total_weight)
    service_ok = service_weight * _SERVICE_DEN >= _SERVICE_NUM * total_weight
    return Evaluation(
        q=q,
        expected_cost=Fraction(purchase_cost) + expected_shortage + expected_waste,
        purchase_cost=purchase_cost,
        expected_shortage_cost=expected_shortage,
        expected_waste_cost=expected_waste,
        service_weight=service_weight,
        total_weight=total_weight,
        service_ok=service_ok,
    )


def optimize(problem: Problem) -> OptimizeResult:
    """返回满足服务约束的全局最低费用 q 及其 evaluate 结果。

    费用相同取较小 q（候选按升序枚举，严格小于才替换）；
    没有任何合法 q 满足服务约束时返回不可行。
    """
    best: Evaluation | None = None
    for q in valid_quantities(problem):
        result = evaluate(problem, q)
        if not result.service_ok:
            continue
        if best is None or result.expected_cost < best.expected_cost:
            best = result
    if best is None:
        return OptimizeResult(feasible=False, q=None, evaluation=None)
    return OptimizeResult(feasible=True, q=best.q, evaluation=best)
