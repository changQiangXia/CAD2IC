# Plan 4：实验可视化与展示图资产收尾

执行状态：已完成（2026-11-10）。

## 0. 目标

本阶段只处理既有实验结果的可视化表达，停止生成新模型任务，保持模型、
题目、预算与官方评分结果原样。

阶段产出：

- A/B/C/D 全量对照图；
- 固定任务三次重复图；
- 置信区间森林图；
- 复杂任务子集图；
- 官方失败分类图；
- round-1 与最终 RTL 修复贡献图；
- CAD 官方指标与类别图；
- 总体架构图；
- benchmark adapter 图；
- 集中展示的 HTML 图册；
- 图表清单与数据来源索引。

## 1. 数据冻结

图表数据源固定为：

| 内容 | 数据源 |
|---|---|
| CAD 指标 | `mac_api_cadtestbench/outputs/.../metrics.csv` |
| CAD 类别 | `mac_api_cadtestbench/outputs/.../evaluations.json` |
| CAD 模型图 | 同一正式 run 的 `figures/` |
| A/B/C/D 全量 | `runs/plan3_results_20261110.json` |
| 三次重复 | `runs/plan3_results_20261110.json` |
| 复杂子集 | `runs/plan3_results_20261110.json` |
| 修复贡献 | `runs/plan3_repair_analysis_20261110/summary.json` |
| VerilogEval 失败码 | 各正式 run 的 `official_eval/results.json` |
| RTLLM 失败状态 | 各正式 run 的 `official_eval/results.json` |

绘图脚本从这些文件读取数值。图表代码禁止写入手工结果数字。

## 2. 表达原则

### 2.1 数据忠实

- 官方分数优先；
- 图表分母保持原始样本数；
- A/B/C/D 使用统一颜色；
- 坐标轴从 0 开始；
- 百分数坐标固定为 0–100；
- 置信区间保留原始方向；
- 图表标题写明 benchmark、模型与口径。

### 2.2 可读性

- 图表标签采用英文，降低中文字体缺失风险；
- 正文说明采用中文；
- PNG 用于文档与 PPT；
- SVG 用于缩放展示；
- HTML 图册用于集中浏览；
- 每张图带数据来源与一句话解释。

### 2.3 口径准确

- CAD 使用 PR、RS、无效样本比例；
- VerilogEval 与 RTLLM 使用官方 `pass@1`；
- assisted 图明确标注 “testbench-assisted”；
- hidden 图明确标注 “testbench-hidden”；
- 负值表示比较方向偏向 first arm，图注说明方向；
- repair 图只使用官方 evaluator 结果；
- MAGE 初始 RTL 缺少可靠恢复路径时标注 `not_recoverable`。

## 3. 视觉资产清单

输出目录：

```text
docs/figures/
docs/visualizations/
```

### 3.1 RTL 主图

1. `rtl_full_2x2.png/.svg`
   - VerilogEval 与 RTLLM 两个 panel；
   - A/B/C/D 四组柱；
   - 柱上标注通过数与百分数。

2. `rtl_repeat_mean_std.png/.svg`
   - 三次重复的平均 pass@1；
   - error bar 使用三次重复标准差；
   - 两个 benchmark panel。

3. `rtl_effect_ci_forest.png/.svg`
   - 全量 confidence interval；
   - architecture hidden、architecture assisted；
   - testbench effect for MAGE、testbench effect for Single；
   - 0 线作为参照。

4. `rtl_repeat_effect_ci.png/.svg`
   - 10 题三次重复的 confidence interval；
   - 与全量 effect 图采用同一颜色和方向。

### 3.2 复杂子集

5. `rtl_complexity_subset.png/.svg`
   - VerilogEval 78 题；
   - RTLLM 25 题；
   - A/B/C/D 四组柱。

### 3.3 失败分析

6. `rtl_failure_codes.png/.svg`
   - VerilogEval 官方结果码；
   - RTLLM 官方失败状态；
   - 每个结果码采用独立颜色。

### 3.4 修复贡献

7. `rtl_repair_analysis.png/.svg`
   - 四类结果：unchanged pass、repair recovery、persistent fail、regression；
   - C/D 两组各自展示 VerilogEval 与 RTLLM；
   - 同时展示全量与三次重复合计。

### 3.5 CAD 主图

8. `cad_official_metrics.png/.svg`
   - PR；
   - RS；
   - invalid sample percentage。

9. `cad_category_accuracy.png/.svg`
   - 官方类别准确率；
   - 每类 passed / total。

10. CAD 正式 run 的既有文件
    - `official_metrics.png`
    - `category_accuracy.png`
    - `generated_stl_gallery.png`
    - `sample_category_01.png` 至 `06.png`
    - `rotatable_cad.html`

现有 CAD 文件采用索引链接，重复图片复制进入 `docs/figures/`。

### 3.6 结构图

11. `project_architecture.svg/.png`
    - CAD 链路；
    - MAGE 链路；
    - 官方 evaluator；
    - RunRecord；
    - A/B/C/D 对照层。

12. `benchmark_adapter.svg/.png`
    - 官方输入；
    - loader；
    - MAGE 稳定 Agent；
    - VerilogEval evaluator；
    - RTLLM evaluator；
    - 替换边界。

结构图采用代码绘制 SVG，保持矢量清晰度。

### 3.7 图册

13. `docs/visualizations/index.html`
    - 分区展示全部图；
    - 每张图提供 PNG、SVG 与源数据链接；
    - 图注写明结论范围；
    - 页面采用响应式布局。

14. `docs/figures/manifest.json`
    - 文件名；
    - 类型；
    - 数据源；
    - 生成时间；
    - 样本数；
    - 说明。

## 4. 视觉规范

### 4.1 配色

| 组 | 颜色 |
|---|---|
| A | `#2F6BFF` |
| B | `#00A6A6` |
| C | `#F59E0B` |
| D | `#8B5CF6` |

辅助色：

- positive：`#2E9D66`
- neutral：`#64748B`
- negative：`#C2413A`
- grid：`#E5E7EB`

### 4.2 尺寸

- 文档图：1800×1000；
- 方形图：1200×1200；
- PNG：200 dpi；
- SVG：保留文字为可编辑文本；
- HTML：最大内容宽度 1280px。

### 4.3 标注

- 柱状图数值保留 1 位小数；
- 置信区间保留 1 位小数；
- 分母与通过数同时展示；
- seed 与固定版本写入图册；
- assisted/hidden 口径写入标题或 subtitle。

## 5. 执行顺序

1. 建立图表数据读取层；
2. 生成 RTL 全量 2×2 图；
3. 生成重复均值与标准差图；
4. 生成全量与重复 CI 森林图；
5. 生成复杂子集图；
6. 生成失败分类图；
7. 生成修复贡献图；
8. 生成 CAD 官方指标与类别图；
9. 生成总体架构与 adapter SVG；
10. 生成 HTML 图册；
11. 更新 README、最终报告与讲稿图片入口；
12. 完成视觉与数据一致性检查。

## 6. 验证

### 6.1 自动验证

- 每个 PNG 文件尺寸正常、文件非零；
- 每个 SVG 文件可解析；
- 每个 HTML 图册图片路径存在；
- 每张图的数据源存在于 manifest；
- 全量柱状图的通过数与 `plan3_results_20261110.json` 一致；
- 重复图均值与标准差和 JSON 一致；
- CI 森林图上下界和 JSON 一致；
- CAD 指标和 `metrics.csv` 一致；
- 图册中的链接可解析；
- 活跃收尾文档禁用字符扫描保持零；
- 工作区 API Key 扫描保持零。

### 6.2 人工验证

- 文字无遮挡；
- 坐标轴标注清晰；
- 颜色对四组一致；
- 图注方向明确；
- PNG 与 SVG 视觉内容一致；
- 图表结论与正式报告一致。

## 7. 停止条件

- 源数据缺失；
- 图表数值与官方结果差异；
- 图片生成失败；
- HTML 图册存在失效链接；
- 图表口径与 assisted/hidden 设置冲突；

## 8. 执行记录

本阶段已完成冻结数据读取、图表生成、图册编排、文档接入与自动验证。

### 8.1 生成资产

- RTL 主图 7 组，每组包含 PNG 与 SVG；
- CAD 重绘图 2 组，每组包含 PNG 与 SVG；
- 总体架构图与 adapter 图 2 组，每组包含 PNG 与 SVG；
- 正式 CAD run 既有资产 10 个，通过图册索引原文件；
- HTML 图册 1 份；
- manifest 1 份，记录源文件、样本数、说明与 SHA256。

核心文件：

```text
docs/figures/
  rtl_full_2x2.png/.svg
  rtl_repeat_mean_std.png/.svg
  rtl_effect_ci_forest.png/.svg
  rtl_repeat_effect_ci.png/.svg
  rtl_complexity_subset.png/.svg
  rtl_failure_codes.png/.svg
  rtl_repair_analysis.png/.svg
  cad_official_metrics.png/.svg
  cad_category_accuracy.png/.svg
  project_architecture.png/.svg
  benchmark_adapter.png/.svg
  manifest.json
docs/visualizations/
  index.html
integration/
  plan4_visualize.py
  test_plan4_visuals.py
```

### 8.2 视觉实现

- 图表使用 1800×1000 画布与 200 dpi PNG；
- SVG 保留可编辑文字节点；
- A/B/C/D 使用统一配色；
- 全量与重复柱状图保留通过数、分母与百分比；
- 森林图保留原始效应方向与 95% bootstrap 区间；
- 失败码图读取正式 evaluator 文件；
- 修复图同时展示全量与三次重复合计；
- CAD 指标读取 `metrics.csv`，类别结果读取 `evaluations.json`。

### 8.3 文档接入

README、最终报告、总体架构、Benchmark Adapter、结果分析和 3 分钟讲稿均已加入
图表入口。完整图册入口为 `docs/visualizations/index.html`。

### 8.4 验证结果

- 11 组重绘图的 PNG 与 SVG 均生成；
- PNG 尺寸均为 1800×1000；
- SVG 解析通过；
- HTML 本地链接全部存在；
- manifest 输出文件与 SHA256 一致；
- 失败码计数与八个正式 evaluator 文件一致；
- 修复聚合计数与官方修复分析 summary 一致；
- CAD 指标与官方 CSV、JSON 一致；
- 活跃交付 Markdown 的禁用字符计数为 0；
- 工作区 API Key 泄漏计数为 0；
- Plan 4 自动测试 12 passed；
- 现有 integration 回归 9 passed。

### 8.5 验收失败条件

- 图中出现手工修改后的结果数字；
- 活跃文档字符串命中禁用字符；
- API Key 出现在图表、HTML 或 manifest。

## 9. 两轮视觉优化

### 9.1 第一轮：信息架构

- 删除图册中重复出现的森林图卡片；
- 将修复图合并到独立审计区；
- 诊断区由三列调整为双列，提高图表标签可读性；
- CAD 主区保留新重绘图、STL 总览与交互模型；
- CAD 原始指标图与六张高密度热图折叠到审计档案；
- CAD 指标改用警示色表达无效样本比例；
- CAD 类别图改用蓝色灰阶体系，与 A/B/C/D 配色分离；
- 最终报告补齐 `D-C` 的 exact McNemar `p=0.4807`。

### 9.2 第二轮：展示层

- 首屏增加深色核心证据卡，突出 VerilogEval-assisted 的正向效应；
- RTL 区增加答辩版四组官方结果表；
- 六个章节加入统一线性图标；
- 效应区间区改用完整图卡，补充标题、PNG、SVG 与源数据入口；
- CAD 生成实体图册与可旋转模型使用清晰标题；
- 增加打印样式、移动端横向表格滚动与锚点留白；
- 图册固定为单一修复入口、单一全量效应入口与单一重复效应入口。

## 10. 最终交付

- 11 组新增静态图，每组提供 PNG 与 SVG；
- CAD 既有 9 张 PNG 与 1 份交互式 HTML 的完整索引；
- 1 份响应式 HTML 图册；
- 1 份图表 manifest；
- README、最终报告与 3 分钟讲稿的图表入口；
- 数据一致性、文件完整性、链接、字符与密钥检查记录。
