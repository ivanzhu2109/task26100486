"""单场景库存仿真。

每日顺序：先报废已到失效日的剩余库存，再接收入库，最后按 FIFO 满足当天需求。
未满足需求计为当天缺货，不结转。第 H 日只执行最后一次报废。
"""
from __future__ import annotations

from collections import deque

from .models import Problem, Scenario


def simulate_scenario(problem: Problem, scenario: Scenario, q: int) -> tuple[int, int]:
    """仿真一个场景，返回 (缺货件数, 报废件数)。"""
    horizon = problem.horizon
    # 按到货日分组固定批次；同日到货保持输入顺序。
    arrivals: list[list[tuple[int, int]]] = [[] for _ in range(horizon)]
    for batch in problem.batches:
        arrivals[batch.arrival].append((batch.expiry, batch.qty))
    # 库存队列：元素为 [失效日, 数量]，按 FIFO 顺序（到货先后，同日按输入顺序）。
    stock: deque[list[int]] = deque()
    shortage = 0
    waste = 0

    for day in range(horizon + 1):
        # 1) 报废失效日为今天的剩余库存（第 H 日仅执行此步）。
        # 队列按到货先后排列而非失效日，需扫描整个队列。
        if stock:
            kept = []
            for expiry, qty in stock:
                if expiry == day:
                    waste += qty
                else:
                    kept.append([expiry, qty])
            stock = deque(kept)
        if day == horizon:
            break
        # 2) 接收入库：第 0 日先收全部固定批次，新订单排在其后。
        for expiry, qty in arrivals[day]:
            if qty > 0:
                stock.append([expiry, qty])
        if day == 0 and q > 0:
            stock.append([problem.new_order_expiry, q])
        # 3) FIFO 满足当天需求；未满足部分计为缺货，不结转。
        remaining = scenario.demand[day]
        while remaining > 0 and stock:
            head = stock[0]
            if head[1] <= remaining:
                remaining -= head[1]
                stock.popleft()
            else:
                head[1] -= remaining
                remaining = 0
        shortage += remaining

    return shortage, waste
