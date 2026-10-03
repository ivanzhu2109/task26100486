"""业务规则定向测试：跨日 FIFO、失效日不可售、MOQ/包装取整、服务不可行。"""
from fractions import Fraction

import pytest

from perishable_inventory import Batch, Problem, Scenario, evaluate, optimize
from perishable_inventory.api import valid_quantities


def base_problem(**overrides) -> Problem:
    params = dict(
        horizon=2,
        batches=(),
        new_order_expiry=2,
        pack=1,
        moq=1,
        max_qty=10,
        cost_per_unit=1,
        shortage_penalty=100,
        waste_cost=1,
        scenarios=(Scenario(1, (0, 0)),),
    )
    params.update(overrides)
    return Problem(**params)


def test_fifo_across_days_old_stock_used_first():
    # 第0日在手 1 件（第2日失效），新订单 1 件；第0日需求 1。
    # FIFO 必须先扣在手库存，新订单留到第2日报废。
    problem = base_problem(
        batches=(Batch(arrival=0, expiry=2, qty=1),),
        scenarios=(Scenario(1, (1, 0)),),
    )
    ev = evaluate(problem, 1)
    assert ev.expected_waste_cost == 1  # 只有新订单报废
    assert ev.expected_shortage_cost == 0


def test_same_day_fixed_batches_consumed_in_input_order():
    # 两个第0日固定批次：先输入的第1日失效，后输入的第2日失效。
    # 第0日需求 1 必须先扣先输入的批次，使其免于报废。
    problem = base_problem(
        batches=(
            Batch(arrival=0, expiry=1, qty=1),
            Batch(arrival=0, expiry=2, qty=1),
        ),
        scenarios=(Scenario(1, (1, 0)),),
    )
    ev = evaluate(problem, 0)
    assert ev.expected_waste_cost == 1  # 仅后输入的批次报废


def test_new_order_queued_after_day0_fixed_batches():
    # 第0日固定批次 1 件（第1日失效），新订单 1 件（第2日失效），需求第0日 1 件。
    # 新订单排在固定批次之后，固定批次被消耗，新订单第2日报废。
    problem = base_problem(
        batches=(Batch(arrival=0, expiry=1, qty=1),),
        scenarios=(Scenario(1, (1, 0)),),
    )
    ev = evaluate(problem, 1)
    assert ev.expected_waste_cost == 1


def test_expiry_day_cannot_sell():
    # 固定批次第1日失效：第1日的需求不能用它满足，只能缺货。
    problem = base_problem(
        batches=(Batch(arrival=0, expiry=1, qty=5),),
        scenarios=(Scenario(1, (0, 3)),),
    )
    ev = evaluate(problem, 0)
    assert ev.expected_shortage_cost == 3 * 100
    assert ev.expected_waste_cost == 5  # 第1日晨全部报废


def test_final_scrap_on_day_H():
    # 新订单失效日 = H = 2：第1日可售，第2日（第H日）仅报废。
    problem = base_problem(scenarios=(Scenario(1, (0, 2)),))
    ev = evaluate(problem, 5)
    assert ev.expected_shortage_cost == 0
    assert ev.expected_waste_cost == 3


def test_unserved_demand_not_backlogged():
    # 第0日缺货不结转到第1日。
    problem = base_problem(scenarios=(Scenario(1, (3, 1)),))
    ev = evaluate(problem, 1)
    # 新订单第0日到货即被需求 3 耗尽：缺货 2；第1日需求 1 再缺货 1
    assert ev.expected_shortage_cost == (2 + 1) * 100
    assert ev.expected_waste_cost == 0


def test_moq_pack_rounding():
    problem = base_problem(pack=4, moq=5, max_qty=13)
    assert valid_quantities(problem) == [0, 8, 12]


def test_invalid_q_rejected():
    problem = base_problem(pack=4, moq=5, max_qty=13)
    for bad in (1, 4, 6, 16, -4):
        with pytest.raises(ValueError):
            evaluate(problem, bad)


def test_service_threshold_boundary_exact():
    # 20 个等权场景，19 个无缺货 -> 恰好 95%，必须判为达标（整数判断，无浮点误差）。
    scenarios = tuple(
        Scenario(1, (0, 0)) if i < 19 else Scenario(1, (5, 5)) for i in range(20)
    )
    problem = base_problem(scenarios=scenarios)
    ev = evaluate(problem, 0)
    assert ev.service_weight == 19
    assert ev.service_ok


def test_infeasible_when_service_unreachable():
    # 需求永远超过供给，任何合法 q 都有缺货场景 -> 不可行。
    problem = base_problem(
        max_qty=2,
        scenarios=(Scenario(1, (10, 10)),),
    )
    result = optimize(problem)
    assert not result.feasible
    assert result.q is None
    assert result.evaluation is None


def test_tie_break_prefers_smaller_q():
    # c=0 时 q=2 与 q=3 费用相同（都满足需求且无报废差异之外的差异）：
    # 构造：需求 (2,0)，w=0，c=0 -> q=2 与 q=3 费用均为 0，取较小 q=2。
    problem = base_problem(
        cost_per_unit=0,
        waste_cost=0,
        scenarios=(Scenario(1, (2, 0)),),
    )
    result = optimize(problem)
    assert result.feasible
    assert result.q == 2
    assert result.evaluation.expected_cost == 0


def test_weighted_average_not_normalized_weights():
    # 权重不必归一化：权重 2:1，期望费用按加权平均。
    problem = base_problem(
        scenarios=(Scenario(2, (1, 0)), Scenario(1, (0, 0))),
    )
    ev = evaluate(problem, 1)
    # 场景一：需求满足，无报废；场景二：报废 1 件
    assert ev.expected_waste_cost == Fraction(1, 3)
    assert ev.expected_cost == Fraction(1) + Fraction(1, 3)
