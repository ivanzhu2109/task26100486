"""题目给定的非凸反例：q=1 是局部低点，全局最优必须是 q=3、期望费用 6.85 分。"""
from fractions import Fraction

from perishable_inventory import Batch, Problem, Scenario, evaluate, optimize


def make_problem() -> Problem:
    return Problem(
        horizon=3,
        batches=(Batch(arrival=1, expiry=2, qty=1),),
        new_order_expiry=3,
        pack=1,
        moq=1,
        max_qty=10,
        cost_per_unit=1,
        shortage_penalty=100,
        waste_cost=1,
        scenarios=(Scenario(95, (0, 0, 0)), Scenario(5, (1, 1, 1))),
    )


def test_local_minimum_at_q1():
    problem = make_problem()
    costs = {q: evaluate(problem, q).expected_cost for q in range(0, 5)}
    # q=1 相对 q=0 与 q=2 是局部低点
    assert costs[1] < costs[0]
    assert costs[1] < costs[2]


def test_global_optimum_is_q3_with_6_85():
    problem = make_problem()
    result = optimize(problem)
    assert result.feasible
    assert result.q == 3
    # 6.85 分 = 137/20，用 Fraction 精确比较，不经过浮点
    assert result.evaluation.expected_cost == Fraction(137, 20)
    assert result.evaluation.service_ok


def test_evaluate_breakdown_at_q3():
    problem = make_problem()
    ev = evaluate(problem, 3)
    assert ev.purchase_cost == 3
    assert ev.expected_shortage_cost == 0
    # 场景一报废 4 件（新订单 3 + 固定批次 1），场景二报废 1 件（固定批次）
    assert ev.expected_waste_cost == Fraction(95 * 4 + 5 * 1, 100)
    assert ev.service_weight == 100
    assert ev.total_weight == 100
