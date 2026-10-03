# perishable_inventory

单 SKU、单门店临期补货优化库。只决定今天（第 0 日）到货的一笔订单量 `q`；
需求预测以有限个加权场景传入，库内不含预测模型。

## 规则摘要

- 天数从 0 计，规划期 `horizon = H`：第 0..H-1 日销售，第 H 日仅执行最后一次报废。
- 每日顺序：先报废已到失效日的剩余库存 → 接收入库 → 按 FIFO 满足当天需求。
- FIFO 按到货先后；同日固定批次按输入顺序；新订单排在第 0 日所有固定批次之后。
- 批次在失效日当天起不可销售；未满足需求计为当天缺货，不结转。
- 固定批次采购成本已发生，不计入费用；报废（含固定批次与新订单）计入处置成本 `w`。
- 合法订单量：`q = 0`，或 `q` 为 `pack` 的整数倍且 `q >= moq`、`q <= max_qty`。
- 服务约束：全程无缺货场景的权重之和 ≥ 总权重的 95%（整数精确判断）。
- 目标费用：`c * q` + 各场景缺货罚金与报废处置费用的加权平均（`Fraction` 精确计算）。

## 使用

```python
from perishable_inventory import Batch, Problem, Scenario, evaluate, optimize

problem = Problem(
    horizon=3,
    batches=(Batch(arrival=1, expiry=2, qty=1),),
    new_order_expiry=3,
    pack=1, moq=1, max_qty=10,
    cost_per_unit=1, shortage_penalty=100, waste_cost=1,  # 整数分
    scenarios=(Scenario(95, (0, 0, 0)), Scenario(5, (1, 1, 1))),
)

ev = evaluate(problem, 3)        # 期望费用、费用分解、服务是否达标
result = optimize(problem)       # 全局最低费用 q；费用相同取较小 q；无解返回 feasible=False
```

## 测试

```bash
python3 -m pytest tests/ -q
```
