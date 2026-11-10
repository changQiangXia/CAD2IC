MAC × CADTestBench：正式运行说明
==============================

运行流程
--------
环境安装 → 实验配置与数据校验 → API 凭据 → MAC 生成与修复 →
最终 STEP 转为 CadQuery → CADTestBench 官方测试 → 指标计算与可视化。

模型固定为 DeepSeek deepseek-flash，使用非思考模式；所有角色使用同一模型。
API 地址：https://api.deepseek.com
密钥环境变量：DEEPSEEK_API_KEY

环境准备
--------
从 mac_api_cadtestbench 项目根目录打开 MAC_API_CADTestBench.ipynb，
保持 third_party、data 和绘图文件与 Notebook 的相对位置。

没有 Jupyter 时，在项目目录的终端运行：
    conda create -y -n mac-eval python=3.12 pip jupyterlab
    conda run -n mac-eval jupyter lab MAC_API_CADTestBench.ipynb

首次将 INSTALL_ENVIRONMENTS=True，只运行环境安装单元。它准备两个环境：
    mac-gen  ：MAC、build123d 和 API 客户端
    mac-eval ：CadQuery、官方评分、Notebook 和绘图

两个环境通过 STEP 和 JSON 交接，隔离 OCP 版本依赖。安装完成后将
INSTALL_ENVIRONMENTS 改回 False，选择“MAC · CADTestBench (eval)”内核，
重启并从顶部依次运行。运行到凭据单元时，通过隐藏输入填写 API Key；
也可以在启动 Jupyter 前设置 DEEPSEEK_API_KEY 环境变量。

实验配置
--------
    N_SAMPLES = 3
    PARTITIONS = ['detailed']
    SEED = 20261101
    REPAIR_BUDGET = 2
    MAX_API_CALLS_PER_TASK = 20
    JUDGE_ENABLED = True

N_SAMPLES 为每分区的样本数，可设为 1–200；None 表示完整 200 题。
abstract 和 detailed 是同一批物体的两种描述，按分区分别评测。
样本顺序由 SEED 和 sample_id 的 SHA256 确定，便于重复选择相同样本。
REPAIR_BUDGET 控制修复次数；MAX_API_CALLS_PER_TASK 限制每题请求尝试次数，
包含失败请求，SDK 自动重试关闭。Judge 是否触发由 MAC 工作流决定。

生成与评分
----------
Notebook 校验固定版本的 MAC 源码、CADTestBench 源码和数据文件。
生成器只接收官方 prompt，官方 CADTests 和评测分数不参与生成或修复。
MAC 在独立进程中生成 CAD，最终 STEP 经桥接导入 CadQuery；桥接不改变几何。

所有生成完成后，使用官方 CADTestBench 实现评测最终产物，计算 PR、RS、
无效样本比例和各类别测试通过率。未生成有效产物的题目仍计入计划样本分母；
已有 STEP 但内部检查失败的题目仍接受官方评测。子集结果按实际样本数报告。

结果与可视化
------------
每次运行在 outputs/ 下创建独立目录，主要内容包括：
    protocol.json             实验配置、样本列表、固定版本和评分规则
    generation_records.json   各题生成状态和产物路径
    metrics.csv               各分区的官方指标汇总表
    evaluations.json          官方评测结果及目录索引
    各题任务目录              MAC 日志、最终状态、CAD 代码及 STEP
    official_evaluation/      官方逐题结果和聚合指标
    figures/                  指标图、CAD 实体图和可旋转 HTML
    plot_index.json           可视化文件索引

Notebook 以官方指标表及可视化收尾。ctb_plots.py 读取官方评分 JSON 绘图，
CAD 图直接使用实际导出的 STL。查看失败原因时，检查对应任务日志和逐题评分文件。

项目来源
--------
MAC：https://github.com/Pan-Chera/Multi-Agent-CAD
固定提交：487f94b7064e935c1a9a2f9b426525d5c94cd857
许可证：third_party/Multi-Agent-CAD/LICENSE

CADTestBench：https://github.com/dimitrismallis/CADTestBench
固定提交：e29283cc61db7329039d95b429766a50bfd37f89
许可证：third_party/CADTestBench/LICENSE

数据：https://huggingface.co/datasets/dimitrismallis/CADTestBench
固定 revision：2b9a4a972d142d2bc634d072e9d4485f171ced06
