# Sci-Glow Video Skill (`sci-glow-video-skill`)

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Agent Skill](https://img.shields.io/badge/Skill-Antigravity%20%7C%20Claude%20Code%20%7C%20Codex-orange.svg)](SKILL.md)

**端到端发光线描硬核科普短视频 AI 制片流水线：从一句话选题 + BGM 音乐文件，全自动直出 60fps 运动模糊母带、双版 4K 封面、文献核查与全平台发布方案。**

本 Skill 沉淀并系统化提炼了 **5 部实测 60s `1080×1440 @ 60fps` 科普成片**（《微流控》《光遗传学》《基因魔剪》《器官芯片》《脑机接口》，独立盲审均分最高 **`9.36 / 10`**）的工程经验与质量护栏，作为 [AzenYes/leaderai-media-toolkit](https://github.com/AzenYes/leaderai-media-toolkit) 的高阶制片编排扩展。

---

## 核心工作流架构

```mermaid
flowchart LR
    S1["1. 零门槛文案与期刊查证"] --> S2["2. BGM 频谱高潮 Drop 对齐"]
    S2 --> S3["3. Carbon 视觉策划 / Argon 编码"]
    S3 --> S4["4. 闪避混音 + 4K 双版安全区封面"]
    S4 --> S5["5. 30fps 量化体检 + 独立只读盲审闭环"]
    S5 -->|P0/P1 != 0 或均分 < 8.5| S3
    S5 -->|0 P0/P1 且均分 >= 8.5| S6["6. 60fps 运动模糊母带直出与交付"]
```

---

## 五大核心增强（相比裸跑基础模板）

1. **BGM 频谱高潮自动卡点 (`analyze-bgm`)**：对任意用户 `.mp3` 自动计算 RMS 与 `<180Hz` 低频包络，精确锁定 **首 Drop（片名卡）→ 情绪低谷 Breakdown → 终极高潮 Drop**，一键导出最佳 `--music-start` 与 Drop 前 `-14dB` 预闪避参数。
2. **量化亮度指纹护栏与 `3:4`/`9:16` 五区防撞**：固化 `bloom: 0.20–0.28`、`K.fog: 0.024–0.028` 等黄金参数，隔离 HUD、Hero 标题、主角区、Callout 安全区（`y∈[880,1080]`）与底部单行字幕，彻底消除过曝、字符折行、`center` 模式 14px 糊影与引线反向穿字。
3. **跨进程限速环境自检 (`preflight`)**：一键排查 Node 18+、FFmpeg、Chrome、Playwright（国内镜像与免重复下浏览器提示），并内置跨进程文件锁限速器按 `1 req/s` 自动补齐 IBM Plex Sans SC 8 个 `.otf` 字重。
4. **零人工“脑补”的独立只读盲审 (`audit-qa`)**：强制派生隔离的只读 `research` 子智能体（禁止接触源码），仅凭 `out/review_rN/` 审片包按 9 维标准打分，严控 **0 P0 / 0 P1 且均分 ≥ 8.5** 方可放行 60fps 渲染。
5. **双模型分工与多选题并行量产**：支持规划模型 + 执行模型接力精制，也支持 Coordinator 派生多路独立 Producer 子智能体（配合 `--workers 4` 并发节流与全局不撞色配色矩阵）单轮并行跑通多条完整科普片。

---

## 仓库目录结构

```text
sci-glow-video-skill/
├── SKILL.md                                  # AI 主控手册与 6 步工作流规范
├── README.md                                 # 本说明文档
├── LICENSE                                   # MIT License
├── .gitignore                                # 严格隔离音频/视频/字体/缓存产物
├── agents/
│   └── openai.yaml                           # Codex 展示名称与简介
├── scripts/
│   └── sci_glow_cli.py                       # 零第三方依赖 Python CLI（5 大子命令）
└── references/
    ├── visual-and-layout-guardrails.md       # 亮度黄金参数、1080×1440 五区坐标与 JS 铁律
    ├── blind-review-protocol.md              # 只读盲审子智能体协议与 9 维评分/P0/P1 标准
    └── multi-agent-batch-playbook.md         # 双模型接力与多选题并发量产操作手册
```

---

## 安装指南

### 前置依赖（必须先安装上游引擎）
本 Skill 依赖 [leaderai-media-toolkit](https://github.com/AzenYes/leaderai-media-toolkit) 中的 `lead-knowledge-animation` 与 `lead-media-script`，以及 [uv](https://docs.astral.sh/uv/)、Node 18+、FFmpeg、Chrome/Playwright、Python `numpy`/`scipy`/`fonttools`。

1. 安装上游工具包（任选方式，例如克隆至本地 skills 目录或按官方 `/plugin install` 流程）。
2. 安装本 Skill（将仓库克隆或联接到所用 Agent 的 skills 目录）：

```bash
# 方式 A：通过 Skills CLI（若宿主支持）
npx skills add zy27488/sci-glow-video-skill

# 方式 B：Git 克隆到本地后建立目录联接 / 复制到全局技能目录
git clone https://github.com/zy27488/sci-glow-video-skill.git
```

常见宿主技能路径对照：
- **Antigravity 2.0**：全局 `~/.gemini/config/skills/sci-glow-video-skill` 或项目 `.agents/skills/sci-glow-video-skill`
- **Claude Code**：全局 `~/.claude/skills/sci-glow-video-skill` 或项目 `.claude/skills/sci-glow-video-skill`
- **Codex / Gemini CLI**：全局 `~/.agents/skills/` 或 `~/.gemini/skills/`

---

## 实测标杆验证数据（5 部 `1080×1440 @ 60fps` 成片）

| 科普选题 | 盲审轮次 | `p99` 亮度峰值 | 高亮占比 (`<=3.5%`) | 均亮 (`17-20`) | 终极结果 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **《微流控》** | 多轮精修定型 | 达标（≥130） | 绿区（≤3.5%） | 绿区 | 确立纵向五区与高潮 Drop 对齐范式 |
| **《光遗传学》** | 双模型协作 | 达标（≥130） | 绿区（≤3.5%） | 绿区 | 跑通 Carbon 策划 + Argon 代码执行分工 |
| **《基因魔剪 CRISPR》** | 5 轮 + 终审 | 达标（≥130） | 绿区（≤3.5%） | 绿区 | 全维度 9–10/10 PASS，P0/P1 清零 |
| **《器官芯片》** | 4 轮盲审 | 达标（≥130） | 绿区（≤3.5%） | 绿区 | 多片并发下全量化体检绿灯放行 |
| **《脑机接口》** | 7 轮严审精修 | 达标（≥130） | 绿区（≤3.5%） | 绿区 | 盲审均分 **`9.36 / 10`**，0 P0/P1 |

---

## 快速使用提示词示例

**1. 单条精制（指定 BGM 与双模型分工）**
```text
请使用 sci-glow-video-skill，制作一支「光遗传学」硬核科普短视频。
规格：60 秒，1080×1440（3:4），中文无配音，使用项目根目录的 bgm.mp3 做频谱高潮卡点与预闪避混音。
要求：先用 analyze-bgm 锁定 Drop 点，严格通过 30fps 量化体检与独立只读盲审闭环（≥8.5 分）后再出 60fps 母带与双版 4K 封面。
```

**2. 多选题并行量产**
```text
请使用 sci-glow-video-skill 的多智能体并行模式，围绕「基因编辑 CRISPR」「器官芯片」「脑机接口」三个选题，
同时派发 3 个独立制片子智能体并行产出 60 秒 1080×1440 @ 60fps 科普全片（各自完成独立盲审与 4K 封面交付）。
```

---

## 致谢与声明

- 底层动画渲染与混音引擎复用 [AzenYes/leaderai-media-toolkit](https://github.com/AzenYes/leaderai-media-toolkit)（MIT License）。
- 本仓库**不包含**任何第三方版权音乐（`.mp3`/`.wav`）或商业字体文件；运行时所需开源字体（IBM Plex Sans SC，SIL OFL 1.1）由用户按需通过限速脚本下载或由上游工具包管理。
