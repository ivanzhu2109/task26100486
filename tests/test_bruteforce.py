"""小规模随机问题与独立穷举参考实现核对。"""
import random
from fractions import Fraction

from perishable_inventory import Batch, Problem, Scenario, evaluate, optimize
from perishable_inventory.api import valid_quantities


# ---------- 独立参考实现（与库内实现结构不同，刻意保持简单直白） ----------

def reference_simulate(problem: Problem, scenario: Scenario, q: int):
    stock = []  # (expiry, qty) 列表，按 FIFO 顺序
    shortage = 0
    waste = 0
    for day in range(problem.horizon + 1):
        # 报废失效日为今天的库存
        next_stock = []
        for expiry, qty in stock:
            if expiry == day:
                waste += qty
            else:
                next_stock.append((expiry, qty))
        stock = next_stock
        if day == problem.horizon:
            break
        # 入库：固定批次按输入顺序；第0日最后追加新订单
        for batch in problem.batches:
            if batch.arrival == day and batch.qty > 0:
                stock.append((batch.expiry, batch.qty))
        if day == 0 and q > 0:
            stock.append((problem.new_order_expiry, q))
        # FIFO 满足需求
        need = scenario.demand[day]
        idx = 0
        while need > 0 and idx < len(stock):
            expiry, qty = stock[idx]
            take = min(qty, need)
            stock[idx] = (expiry, qty - take)
            need -= take
            idx += 1
        stock = [(e, n) for e, n in stock if n > 0]
        shortage += need
    return shortage, waste


def reference_evaluate(problem: Problem, q: int):
    total_weight = sum(s.weight for s in problem.scenarios)
    cost_sum = 0
    service_weight = 0
    for scenario in problem.scenarios:
        shortage, waste = reference_simulate(problem, scenario, q)
        cost_sum += scenario.weight * (
            shortage * problem.shortage_penalty + waste * problem.waste_cost
        )
        if shortage == 0:
            service_weight += scenario.weight
    expected = Fraction(problem.cost_per_unit * q) + Fraction(cost_sum, total_weight)
    service_ok = service_weight * 20 >= 19 * total_weight
    return expected, service_ok


def reference_optimize(problem: Problem):
    best_q = None
    best_cost = None
    for q in valid_quantities(problem):
        cost, ok = reference_evaluate(problem, q)
        if ok and (best_cost is None or cost < best_cost):
            best_q, best_cost = q, cost
    return best_q, best_cost


# ---------- 随机问题生成 ----------

def random_problem(rng: random.Random) -> Problem:
    horizon = rng.randint(1, 4)
    batches = tuple(
        Batch(
            arrival=(arrival := rng.randint(0, horizon - 1)),
            expiry=rng.randint(arrival + 1, horizon),
            qty=rng.randint(1, 4),
        )
        for _ in range(rng.randint(0, 3))
    )
    scenarios = tuple(
        Scenario(
            weight=rng.randint(1, 9),
            demand=tuple(rng.randint(0, 4) for _ in range(horizon)),
        )
        for _ in range(rng.randint(1, 3))
    )
    pack = rng.randint(1, 3)
    return Problem(
        horizon=horizon,
        batches=batches,
        new_order_expiry=rng.randint(1, horizon),
        pack=pack,
        moq=rng.randint(1, 5),
        max_qty=rng.randint(0, 12),
        cost_per_unit=rng.randint(0, 5),
        shortage_penalty=rng.randint(1, 100),
        waste_cost=rng.randint(0, 5),
        scenarios=scenarios,
    )


def test_random_problems_match_reference():
    rng = random.Random(20261003)
    infeasible_seen = 0
    for _ in range(300):
        problem = random_problem(rng)
        # 每个合法 q 的 evaluate 都要与参考实现一致
        for q in valid_quantities(problem):
            ev = evaluate(problem, q)
            ref_cost, ref_ok = reference_evaluate(problem, q)
            assert ev.expected_cost == ref_cost, (problem, q)
            assert ev.service_ok == ref_ok, (problem, q)
        # optimize 结果与参考穷举一致
        result = optimize(problem)
        ref_q, ref_cost = reference_optimize(problem)
        if ref_q is None:
            infeasible_seen += 1
            assert not result.feasible
        else:
            assert result.feasible
            assert result.q == ref_q
            assert result.evaluation.expected_cost == ref_cost
    # 确认随机样本中确实覆盖了"所有合法 q 均不可行"的情况
    assert infeasible_seen > 0
