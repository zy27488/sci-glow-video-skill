# 双模型协作与多选题并行量产指南（Multi-Agent Playbook）

本指南固化自高分单条精制（Carbon + Argon 分工）以及单回合 3 条 60s 科普全片并发跑通的实战经验。

---

## 1. 单条精制：双模型（Planning + Execution）职责切分

当宿主支持高低搭配双模型（如 **Carbon / Pro 做规划，Argon / Sonnet / Flash 做工程执行**）时，按如下边界接力：

| 阶段 | 负责角色 | 核心输出物与决策权 |
| :--- | :--- | :--- |
| **Stage 1–2：选题、文献核查与 BGM 卡点** | **策划模型（Carbon）** | 锁定反直觉钩子数字、验证 `Nature/Science` 等真实出处；结合 `analyze-bgm` 输出定下全片 4 个核心情绪锚点（Hook / Title Drop / Breakdown / Climax Drop） |
| **Stage 3A：视觉识别与专属图元蓝图** | **策划模型（Carbon）** | 设计不撞色的 5–6 色 Token 盘、定下贯穿全片的隐喻主角与 `core.js` 专属绘制原语结构（3–5 细节层） |
| **Stage 3B：确定性引擎实现与排版** | **执行模型（Argon）** | 实现 `core.js` + `scenes.js`（IIFE 封装）+ `index.html` + `cover.html`；执行 `fonts.py`、`verify.mjs`、`cover.mjs --guides` 与 `mix.py` |
| **Stage 5：30fps QA 与盲审闭环** | **Argon + 只读盲审子智能体** | Argon 出 `30fps` 草稿并跑 `audit-qa`；派生只读 `research` 子智能体盲审，Argon 按 P0/P1 清单闭环修图直至 `>= 8.5`（架构级重做才升级回 Carbon） |
| **Stage 6：60fps 母带交付** | **执行模型（Argon）** | 一次性渲染 `--fps 60 --blur 2 --audio work/mix.wav`，核验后清理 `draft*.mp4` 并总结人耳确认时间点 |

---

## 2. 多选题并行量产模式（Coordinator + N × Producer Subagents）

当用户需要同时产出 2–4 个不同选题的科普视频时，主智能体扮演 **Coordinator（调度官）**：

### 2.1 前置公共对齐（Coordinator 一次性完成）
1. 运行 CLI `preflight`，确保上游技能、Playwright 与 IBM Plex Sans SC 8 字重就绪。
2. 若共用同一首 BGM，先跑一次 `analyze-bgm`，将算出的推荐 `--music-start` 与卡点结构模板统一分发给各子智能体（仍允许不同主题根据叙事微调）。
3. **全局去重美学矩阵**：Coordinator 在派发前为各片分配互不重复的 **主色调与视觉隐喻原型**，避免同批成片撞脸（例如：《基因魔剪》用基因金 × 冷青双螺旋；《器官芯片》用肺泡微流紫 × 氧青；《脑机接口》用神经电青 × 意念暖金）。

### 2.2 独立 Producer 子智能体隔离派工
为每个选题派发 1 个独立的 `self` 类型 Producer 子智能体，必须严格指定：
- **隔离路径**：各自的 `口播文案输出/<YYYYMMDD 主题科普>/` 与 `.code/<YYYYMMDD 主题科普动画>/`，严禁跨片交叉读写文件。
- **并发渲染节流（关键）**：Playwright Chromium 多线程渲染高度消耗内存与 CPU。**3–4 个片子同时并发时，每个片子执行 `render.mjs` 务必显式传 `--workers 4`**（即便宿主机有 24 核），防止内存溢出或 Chromium 假死；若单机仅做 1 条片，可放开至 `--workers 8`。
- **强制独立盲审自检**：每个 Producer 子智能体在渲染 `60fps` 母带前，都**必须在自己的任务内再派生一个只读 `research` 盲审子智能体**审查自己的 `out/review_r<N>/`，拿到 0 P0/P1 且均分 `>= 8.5` 后才允许提交 60fps 终版。

### 2.3 汇总验收（Coordinator Final Gate）
Coordinator 收到全部 Producer 完成通知后：
1. 对每部最终 `.mp4` 再运行一次 CLI `audit-qa` 核验母带亮度指纹与响度（`-14±1 LUFS / <=-1 dBFS`）；
2. 查看每部成片的 4K 横竖封面与联系表图像；
3. 向用户统一汇报每部片子的成片路径、量化指标、盲审评分、4K 封面、分平台文案路径及人耳重点复核时间戳。
