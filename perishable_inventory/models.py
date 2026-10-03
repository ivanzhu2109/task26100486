"""数据类型定义：问题输入与评估结果。"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Optional, Tuple


@dataclass(frozen=True)
class Batch:
    """固定批次（含第0日在手库存）。采购成本已发生，不计入费用。"""
    arrival: int   # 到货日，0 <= arrival < H
    expiry: int    # 失效日，arrival < expiry <= H；失效日当天起不可销售
    qty: int       # 数量，正整数


@dataclass(frozen=True)
class Scenario:
    """需求场景：正整数权重 + H天整数需求。"""
    weight: int
    demand: Tuple[int, ...]


@dataclass(frozen=True)
class Problem:
    """单SKU、单门店临期补货问题。"""
    horizon: int                 # H，规划期天数（第0..H-1日销售，第H日仅报废）
    batches: Tuple[Batch, ...]   # 固定批次，所有场景相同
    new_order_expiry: int        # 新订单失效日，1 <= expiry <= H
    pack: int                    # 包装量，正整数
    moq: int                     # 最小起订量，正整数
    max_qty: int                 # Q，采购上限
    cost_per_unit: int           # c，每件新增采购成本（分）
    shortage_penalty: int        # p，每件缺货罚金（分）
    waste_cost: int              # w，每件报废处置成本（分）
    scenarios: Tuple[Scenario, ...]


@dataclass(frozen=True)
class Evaluation:
    """evaluate 的返回结果。"""
    q: int
    expected_cost: Fraction      # 期望总费用（分），精确有理数
    purchase_cost: int           # c * q
    expected_shortage_cost: Fraction
    expected_waste_cost: Fraction
    service_weight: int          # 全程无缺货场景的权重之和
    total_weight: int            # 全部场景权重之和
    service_ok: bool             # service_weight / total_weight >= 95%（整数精确判断）


@dataclass(frozen=True)
class OptimizeResult:
    """optimize 的返回结果。feasible=False 时 q 与 evaluation 为 None。"""
    feasible: bool
    q: Optional[int]
    evaluation: Optional[Evaluation]
