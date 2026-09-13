---
name: mindmap-answer
description: 将自然语言问题整理为结构化左右对开思维导图并渲染图片，适用于思维导图、导图回答、mindmap、结构化扫读、用导图回答、画一张导图等请求
metadata:
  short-description: 结构化导图回答与静态图片渲染
---

# 导图回答

进入导图回答模式。先建树，再渲染，禁止先写长文。

## 工作流

1. 判断题型为解释、对比、规划、排查或流程，并按 [回答契约](references/answer-contract.md) 的题型路由拆解。
2. 遇到强时序、协议交互或状态机时，只在导图中保留阶段骨架，并在文本中说明完整表达应改用 flowchart 或 sequence diagram；不要硬画成放射关系。
3. 压缩根标题，不要照抄用户原问题。
4. 拆出 5–9 个一级枝并标上 ①–⑨。对比题按维度拆，解释题按框架拆，不要把流水账时间线当一级结构。
5. 默认使用 3 层。只有关键路径且用户确实需要细节时，才允许最多 2 条一级枝下探到 4–5 层。若 L3 及以上节点总数超过 18，收回为总图只到 L2，并指出可另行展开的枝。
6. 将节点压缩为中文 2–8 字或英文 1–6 词，硬上限 12 字符；保持同级词性一致，不写完整句子，不用“其他”“补充”“总结”作为一级枝。
7. 写出不超过 40 字的 `conclusion` 和 3–6 条 `reading_path`。
8. 按 [回答契约](references/answer-contract.md) 建立 UTF-8 JSON。不要在节点中放颜色或坐标。
9. 先运行 `scripts/validate_tree.py`，再调用 `scripts/render_mindmap.py`。布局与视觉必须遵守 [布局算法](references/layout-algorithm.md) 和 [视觉规格](references/visual-spec.md)。
10. 渲染失败时，按错误修树并只重试一次。仍失败则说明错误，不要交付坏图。
11. 按“结论 → 阅读路径 → 结构大纲 → 思维导图”回复。大纲必须与 JSON 同构，并给出生成图片的绝对路径。

## 命令

```bash
python scripts/render_mindmap.py --input path/to/tree.json --out artifacts/mindmap.png --also-jpg
```

不要使用 Mermaid 或 Markmap 作为终稿。不要加入旋转文字、emoji、图标、手绘线、彩虹渐变、网格、水印、装饰插画或交互折叠。
