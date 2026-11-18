---
name: sci-glow-video-skill
description: >-
  端到端发光线描科普短视频制片工作流（60fps 确定性动画、零配音逐字字幕、BGM 频谱高潮卡点与闪避混音、双版 4K 封面、量化亮度体检与独立子智能体盲审闭环，支持多选题并行量产）。在
  Lead-自媒体口播文案 与 Lead-知识讲解动画 基础上，固化文献事实核查、MP3 高潮 Drop 自动对齐、Carbon 策划 + Argon 实现双模型分工、3:4/9:16
  纵向五区防撞排版、bloom 亮度护栏与 P0/P1 零缺陷放行标准。当用户要求制作硬核科普动画、发光线描科学讲解视频、跟随 BGM 高潮卡点的知识短视频，或批量生产系列科普动画时使用。
license: MIT
metadata:
  version: "1.0.0"
  display-name: "Sci-Glow 发光线描科普视频制片"
  author: "zy27488"
---

# Sci-Glow Video Skill (发光线描科普视频全流程制片)

## Overview

将硬核科学选题从“一句话概念”稳定转化为可直接发布的 **60 秒（或指定时长）发光线描科普动画全套交付物**：纯文字口播方案、文献核查表、精确卡点字幕稿、60fps 运动模糊母带 MP4、横竖双版 4K 安全区封面，以及分平台运营文案。

核心哲学：**硬质量门禁自动返工（量化亮度 + 零 BOM 校验 + 独立只读子智能体盲审 ≥ 8.5 分）**，绝不在存在 P0/P1 缺陷或过曝灰屏时强行渲染母带。

## Dependencies

本 Skill 编排并增强以下上游能力，不重复实现其底层引擎：

- **`Lead-知识讲解动画` (`lead-knowledge-animation`)**：提供确定性 Canvas/DOM 运行时（`motion.js`、`kit.js`）与底层脚手架（`new_film.mjs`、`beats.py`、`timeline.py`、`fonts.py`、`sfx.py`、`mix.py`、`render.mjs`、`cover.mjs`、`verify.mjs`、`qa_video.py`、`review_pack.py`）。来自 `AzenYes/leaderai-media-toolkit`。
- **`Lead-自媒体口播文案` (`lead-media-script`)**：提供冷开场钩子语法、生活化类比表达结构与 B 站/抖音/视频号/小红书/YouTube 分平台发布文档规范。来自 `AzenYes/leaderai-media-toolkit`。
- **`uv` (`uv run`)**：运行本 Skill 配套的纯标准库辅助 CLI 脚本 `scripts/sci_glow_cli.py`。
- **可选科研检索技能**（宿主已安装时优先调用）：`pubmed-database` 或 `literature-search-openalex`，用于核查权威论文期刊与真实数值；未安装时使用联网搜索核实一级文献。

## Quick Start

```bash
# 1. 环境与 IBM Plex Sans SC 8 字重自检（缺字体时自动限速拉取）
uv run <skill_dir>/scripts/sci_glow_cli.py preflight --auto-fix-fonts --output work/preflight.json

# 2. 对任意用户 MP3 做频谱高潮测算，输出 Top-3 截取起点与预闪避参数
uv run <skill_dir>/scripts/sci_glow_cli.py analyze-bgm --bgm "<BGM.mp3>" --target-duration 60 --top-k 3 --output work/bgm_analysis.json

# 3. 初始化工程双目录并写入安全默认参数（含 3:4 1080x1440 与 bloom 0.26）
uv run <skill_dir>/scripts/sci_glow_cli.py scaffold-project --workspace "<项目根目录>" --date 20261118 --topic 光遗传学 --ratio 3x4 --output work/scaffold.json
```

## Utility Scripts

所有辅助计算均通过 `scripts/sci_glow_cli.py` 提供，统一用 `--output` 写出 **UTF-8 无 BOM JSON**，禁止向终端吐出大段原始日志：

| 子命令 | 核心作用 | 关键必填参数 |
| :--- | :--- | :--- |
| **`preflight`** | 检查 Node 18+、FFmpeg、Chrome、Playwright（提示 `npmmirror` + 跳过重复下浏览器）、上游双技能及 IBM Plex 8 字重；加 `--auto-fix-fonts` 自动补齐 `.otf` | `--output` |
| **`scaffold-project`** | 建立 `口播文案输出/<日期 主题科普>/` 与 `.code/<日期 主题科普动画>/`，运行 `new_film.mjs` 并打补丁启用 `3:4` 尺寸与 `bloom: 0.26` | `--workspace`, `--date`, `--topic`, `--ratio`, `--output` |
| **`analyze-bgm`** | 用 FFmpeg 解码 8kHz 单声道波形，提取全频 RMS + `<180Hz` 低频包络，搜索 **Drop 1（片名卡）→ Breakdown → 终极高潮 Drop**，输出 Top-K `--music-start` 与 `--music-dips` | `--bgm`, `--target-duration`, `--top-k`, `--output` |
| **`validate-lines`** | 校验/剔除 UTF-8 BOM，检查 `1080px` 宽下字数（钩子 `<=12` 字、字幕 `<=15` 字）、平衡括号、无句末标点与 `5s` 钩子上限，自动反算锁死总时长 `tail` | `--lines`, `--target-duration`, `--ratio`, `--output`（可选 `--fix-bom`, `--apply-tail`） |
| **`audit-qa`** | 调用上游 `qa_video.py` 并按黄金指纹（`mean 17-20`、`p99 >= 130`、`bright <= 3.5%`、零死区、零闪帧）给出红绿灯与调参处方，并生成独立盲审提示词 | `--video`, `--film-dir`, `--round`, `--output` |

## Workflow

遇到多选题并行需求或双模型分工时，同时加载 [multi-agent-batch-playbook.md](references/multi-agent-batch-playbook.md)；画面与排版参数严守 [visual-and-layout-guardrails.md](references/visual-and-layout-guardrails.md)。

### Step 0: 开工前环境体检与音乐确认
1. 运行 `preflight --auto-fix-fonts --output ...`；若缺少 Playwright，引导执行：
   `$env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD="1"; npm i playwright --registry https://registry.npmmirror.com`。
2. 音乐门禁：若用户指定了曲子就只用用户的；未指定且本机无配套曲时，主动询问用户补充音乐文件路径或改用纯音效（不私自跳过）。

### Step 1: 零门槛文案撰写与一级文献核查（复用 `Lead-自媒体口播文案`）
1. 前 3 秒必须用具体数字/反直觉事实抓人，随后先给日常具象类比再引入科学术语。
2. 核查至少 2–3 篇一级期刊出处（`Nature` / `Science` / `NEJM` / `Cell`），严禁编造数据。
3. 在 `口播文案输出/<YYYYMMDD 主题科普>/` 生成纯文案 `.txt` 与执行方案 `.md`。

### Step 2: BGM 频谱高潮对齐与字幕精确锁时长
1. 运行 `analyze-bgm --bgm <path> --target-duration <T> --top-k 3 --output work/bgm.json` 选中最佳 `music_start_sec`，并用上游 `beats.py` 输出 `work/beats.json`。
2. 编写 `work/lines.json`：把片名卡 `T.at` 卡在 **Drop 1**，转折危机 `at` 卡在 **Breakdown**，突破瞬间 `at` 卡在 **终极高潮 Drop**，末尾留出回调意象收尾。
3. 运行 `validate-lines --lines work/lines.json --target-duration <T> --ratio <ratio> --fix-bom --apply-tail --output work/lines_check.json`，全绿后再跑上游 `timeline.py --beats work/beats.json --music-start <start> --film film/`。

### Step 3: 视觉系统设计与确定性代码实现（复用 `Lead-知识讲解动画`）
> [!IMPORTANT]
> 编码与视觉参数必须遵守 [visual-and-layout-guardrails.md](references/visual-and-layout-guardrails.md)：`bloom: 0.20–0.28`、`K.fog: 0.024–0.028`、`K.hud.corner` 禁用、`scenes.js` 包裹 IIFE、转场标题采用 `mode: 'rise', blur: 0` 并延后 `+0.36s`。

1. 先运行 `scaffold-project` 建立双目录。
2. 设计不撞色的主体色板，在 `film/core.js` 中为本片专属科学隐喻手写 3–5 层发光精细原语（禁止重复通用方框卡片/火柴人）。
3. 编写 `film/scenes.js`、`film/index.html` 与 `film/cover.html`，跑通上游 `fonts.py film/` 子集化与 `verify.mjs film/index.html --tol 24` 全点零差校验。

### Step 4: 闪避混音与双版 4K 封面安全区检验
1. 用 **UTF-8 无 BOM** 写出 `work/cues.json`，执行 `sfx.py --variants 3` 与 `mix.py`（填入 `analyze-bgm` 给出的 `--music-start` 与 `--music-dips`，对齐 `-14.0 LUFS / -1.5 dBFS`）。
2. 执行 `cover.mjs film/cover.html --out out --name <主题> --guides`，**亲眼查看 `work/封面检查/` 图像**，确保横版关键信息严格落在中央 `4:3`（`x ∈ [240, 1680]`）内。

### Step 5: 30fps 草稿量化体检 + 独立只读子智能体盲审闭环
> 详见 [blind-review-protocol.md](references/blind-review-protocol.md)。

1. 先出半分辨率草稿：`render.mjs film/index.html --fps 30 --scale 0.5 --out out/draft_r1.mp4`（单片可用 `--workers 8`，多片并发严控 `--workers 4`）。
2. 运行 `audit-qa --video out/draft_r1.mp4 --film-dir film --round 1 --output work/qa_r1.json`。亮度或死区未达标时先直接按处方改参数重出草稿。
3. 执行 `review_pack.py out/draft_r1.mp4 --film film/ --out out/review_r1`，派生只读 `research` 盲审子智能体（**仅可读取 `out/review_r1/`，严禁看源码**）执行 9 维打分。
4. 存在任何 **P0/P1** 或 **均分 `< 8.5`** 时**严禁出 60fps 母带**，逐项修改、自检、重审直到全绿。

### Step 6: 60fps 运动模糊母带直出与完整交付
1. 盲审全绿后仅渲染一次终版：`render.mjs film/index.html --fps 60 --blur 2 --audio work/mix.wav --out out/<主题>.mp4`。
2. 再跑一次 `audit-qa` 与 `qa_video.py --sheet --ref-sheet`，亲眼检查成片联系表并删除 `out/draft*.mp4` 临时草稿。
3. 按 `Lead-自媒体口播文案` 与 `copy_template.md` 完成 `work/文案与封面.md`，向用户交付全套文件及需要人耳试听的音频重拍时刻清单。

## Rate Limiting

- `analyze-bgm`、`validate-lines`、`scaffold-project`、`audit-qa` 全部在本地运行，无外部网络请求。
- `preflight --auto-fix-fonts` 从 CDN 拉取缺失 `.otf` 字体时，内置**跨进程 OS 文件锁 + `time.monotonic()` 速率限制器（`1.0 req/s`）**，对 5xx 实施 3 次指数退避重试，遇到 HTTP 429 抛出 `RateLimitError` 并终止请求。

## Common Mistakes

1. **PowerShell UTF-8 BOM 导致 `mix.py` 崩溃**：PowerShell 5.1 默认 `Set-Content -Encoding UTF8` 会写入 `EF BB BF` 文件头。所有 `.json` 务必由 Python `encoding='utf-8'`、`cli` 工具或 `[IO.File]::WriteAllText`（不带 BOM）写入。
2. **沿用默认 `bloom: 0.9` 与 `mode: 'center'` 糊影**：大发光线描主体配 `0.9` 辉光必炸 `bright > 3.5%`，`center` 标题写死 14px 模糊必毁光扫转场。必须按 [visual-and-layout-guardrails.md](references/visual-and-layout-guardrails.md) 下调至 `0.20–0.28` 并改用 `rise`（`blur: 0`）。
3. **多片并发时 Chromium Workers 过载与“自己审自己”**：3–4 片并行必须限流 `--workers 4`；同时绝不可由写代码的同一上下文自评放行，必须经由隔离目录 `out/review_rN/` 的只读盲审子智能体签字通过。
