# task26100486

单 SKU、单门店的临期补货优化库。只决定今天（第 0 日）到货的一笔订单量 `q`；
需求预测以有限个加权场景传入，不含预测模型。

## 接口

- `evaluate(problem, q)`：评估给定订单量的期望费用（`fractions.Fraction`，单位分）
  与服务约束是否达标。
- `optimize(problem)`：枚举全部合法 `q`，返回满足服务约束的全局最低费用解；
  费用相同取较小 `q`，无解返回 `feasible=False`。

## 规则摘要

- 天数从 0 计，规划期 H 天；第 H 日只执行最后一次报废。
- 每日顺序：报废到失效日的剩余库存 → 接收入库 → 满足当天需求。
- 严格按到货先后 FIFO 扣减；同日固定批次按输入顺序，新订单排在第 0 日
  所有固定批次之后。批次在失效日不可销售。缺货不结转。
- `q` 必须为 0，或至少达到 MOQ 的 pack 整数倍且不超过 Q。
- 服务约束：全程无缺货场景的权重之和 ≥ 总权重的 95%（整数精确判断）。
- 目标费用 = `c*q` + 各场景缺货罚金与报废处置费用的加权平均
  （固定批次采购成本已发生，不计入）。全程使用 `Fraction` 精确运算，
  费用比较与 95% 边界不受浮点舍入影响。

## 示例

```python
from perishable import Batch, Problem, Scenario, evaluate, optimize

problem = Problem(
    horizon=3,
    batches=(Batch(arrival_day=1, expiry_day=2, quantity=1),),
    new_order_expiry=3,
    pack=1, moq=1, max_order=10,
    unit_cost=1, shortage_penalty=100, disposal_cost=1,
    scenarios=(
        Scenario(weight=95, demand=(0, 0, 0)),
        Scenario(weight=5, demand=(1, 1, 1)),
    ),
)

result = optimize(problem)
assert result.q == 3
assert float(result.evaluation.expected_cost) == 6.85
```

## 测试

```bash
python3 -m pytest tests/ -q
```
