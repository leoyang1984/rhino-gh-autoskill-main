# Checkpoint — 项目进度快照

> 产品队列由人工维护；Recipe 指标仅在标记区块内由同步脚本生成。
> 新 session 开始时读此文件，快速了解项目当前位置，无需回溯历史。

---

## 当前阶段

**L4.5 已完成（2026-04-13）→ L5 起点**

- 第一批 Recipe：9/9 全部验证通过
- 链式组合测试：6 对通过
- Recipe v2 公共接口与 `composition_rules` 组合机制：已建立

---

## 上次操作

新 Recipe 入库：`kangaroo-cloth`（布料重力模拟，2026-08-13）——项目首个 Kangaroo 物理模拟 Recipe，经 MCP 全链路验证（拓扑 30 节点/43 线，形态经用户确认）。
已知瑕疵：顶部网格边缘有碎边（需多模态视觉模型精细处理，暂不调整）。
物理模拟求解协议（Reset/On 时序、数值审计）见 `knowledge/kangaroo-physics-patterns.md`。
此前：工程优化完成（Recipe v2、统一验证器、类型检查、组合器、健康检查、动态审计与准入门禁，2026-08-13）。

---

## 下一步

第二批进行中。下一个推荐：
1. `facade-perforate` — 参数化穿孔幕墙
2. `floor-offset` — 楼板偏移/错层
3. `core-place` — 核心筒布置

---

## 待完成链式测试

（暂无，持续积累中）

---

## Recipe 计数

<!-- GENERATED:RECIPE-STATUS:START -->
| 指标 | 数量 |
|---|---:|
| Recipe 总数 | 18 |
| verified | 18/18 |
| schema v2 | 18/18 |
| 静态验证通过 | 18/18 |
| 公共组合规则 | 8 |

此区块由 `scripts/sync_project_status.py` 生成；产品队列和下一步仍由人工维护。
<!-- GENERATED:RECIPE-STATUS:END -->
