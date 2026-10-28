# Auto Video Agent

**多模态 Agent 自动视频剪辑系统**

输入一句视频需求，自动完成素材准备、内容理解、剪辑规划、旁白字幕制作和成片导出。

> 示例：“制作一条 60 秒校园宣传片，风格清新，横屏，带中文旁白和字幕。”

本仓库基于 [Crayotter](https://github.com/idwts/Crayotter) 视频 Agent 工作流进行个人开发与工程化改造，重点迭代 FastAPI 后端、Vue 3 工作台、视频分析可靠性及任务执行架构。

[仓库地址](https://github.com/lnzz21/auto-video-agent) · [完整代码](https://github.com/lnzz21/auto-video-agent/tree/main) · [架构说明](docs/architecture_cn.md) · [提交与分支整理](docs/git-history.md)

## 项目能力

| 能力 | 实现内容 |
|---|---|
| 自然语言驱动 | 根据主题、时长、画幅、风格、旁白与字幕要求生成执行计划 |
| 素材准备 | 支持本地素材、用户链接导入及平台搜索，统一筛选和下载 |
| 多模态视频理解 | 分析画面和时间范围，保存可检索的片段描述 |
| 三阶段 Agent 工作流 | 素材准备、剪辑研究、受控执行分别承担明确职责 |
| 资源感知调度 | 通过 DAG 依赖、资源池和冲突键安排任务执行 |
| 恢复与复用 | 持久化检查点和产物清单，验证历史任务与文件后复用结果 |
| 人工参与 | 支持剪辑计划审阅、计划修订及运行中补充要求 |
| 成片处理 | 完成裁剪、合并、转场、TTS、混音、字幕和导出 |
| 运行可观测 | 保存结构化事件、日志、中间产物和评估结果，供工作台查看 |

## 工作流程

### 1. 素材准备

Planner 根据用户需求生成结构化计划，由执行器转换成任务 DAG。

- 搜索分支可在资源容量内并发运行。
- 候选排序等待搜索结果汇总。
- 单个视频下载完成后，才能进入对应分析任务。
- 素材评估器检查数量、可用时长、分析完整性、主题与画幅适配等信息。
- 评估结果分为继续、有限轮次补充和失败，补充时保留仍可用的素材与成果。

### 2. 剪辑研究与计划审阅

研究阶段读取素材分析，形成叙事、视觉连续性、节奏和旁白策略，再整合成剪辑蓝图。

该阶段不执行剪辑工具。后续可生成结构化剪辑计划，完成校验、用户审阅和版本冻结。启用方式由运行配置决定。

### 3. 受控执行与回退

优先将剪辑计划转换为受控 DAG：

- 独立片段裁剪、预处理和分段 TTS 可按资源限制并发。
- 主时间线合成、混音、字幕和导出遵循产物依赖与写入互斥。
- 受控路径失败后，根据条件进入短片结构化执行或 ReAct 回退。
- 候选成片经对应路径评估后，登记为被接受的最终产物。

## 技术实现

### Agent 编排与状态

使用 LangGraph 管理阶段流转和重新规划，使用 Pydantic 定义需求、计划、任务与状态对象。模型负责规划和判断，确定性执行器负责调用工具、操作文件及登记产物。

恢复能力主要来自自建调度检查点与产物注册表；这些能力与阶段图的状态路由分别实现。

### 资源感知 DAG 调度

每个 `TaskSpec` 声明依赖、参数、资源需求、冲突键、产物类型和重试策略。共享调度器检查依赖及循环关系，在资源可用时统一申请资源，再提交到有上限的线程池。

| 资源池 | 主要任务 |
|---|---|
| `search_pool` | 素材搜索 |
| `download_pool` | 视频下载 |
| `video_analysis_pool` | 多模态视频分析 |
| `llm_pool` | 规划与研究 |
| `ffmpeg_pool` | 视频裁剪、合成及媒体处理 |
| `tts_pool` | 旁白生成 |
| `export_pool` | 最终导出 |

可能写入同一路径的任务使用冲突键互斥。资源配置来自运行配置及对应的 `CRAYOTTER_*_POOL_SIZE` 环境变量。

### 任务恢复与产物复用

检查点保存任务状态、执行结果、任务指纹、依赖指纹和产物 ID；产物注册表保存路径、类型、生产任务、元数据及校验信息。

恢复时检查任务定义、依赖及实际文件有效性，决定复用还是重跑。分析结果、已下载素材和有效中间文件可以继续参与后续执行。

当前文件摘要基于文件大小和前 1 MiB 内容，属于轻量完整性检查。处理预算为软预算；取消和超时还依赖底层网络请求、子进程及协作式检查。

### 视频理解与文本片段检索

`analyze_video` 调用多模态模型生成带时间范围的画面描述，保存为 `*_analysis.json`。片段包含：

```json
{
  "start": 24.0,
  "end": 40.0,
  "duration": 16.0,
  "semantic_text": "学生从校门进入校园，晨光、广角镜头，氛围积极"
}
```

检索工具根据剪辑意图，对片段描述进行 token 重合、短语包含和时长偏好评分，返回源视频与起止时间，再交给裁剪工具。

当前使用轻量文本检索，尚未接入向量数据库。分析描述按模型生成的时间段保存，其精度取决于模型输出。

### 旁白、字幕与媒体检查

- TTS 旁白按文字和时间计划生成，受控路径可复用预先生成的分段音频。
- 字幕主要沿用旁白计划，以 MoviePy 文字图层合成进成片。
- 支持旁白时段背景音压低和响度归一化。
- 媒体检查覆盖时长、画幅、编码及相应的解码、黑帧、冻结和响度指标。
- 技术检查与内容审阅分别承担可播放性检查和创作质量判断。

## 27 个注册工具

实际工具范围以 [`ALL_TOOLS`](script/tools/__init__.py) 为准，按阶段选取可用工具。

| 类别 | 工具 |
|---|---|
| 素材准备（6） | `search_material_sources`、`import_material_urls`、`download_material_video`、`search_bilibili_video`、`download_bilibili_video`、`rank_video_candidates` |
| 内容理解（2） | `analyze_video`、`recall_semantic_segments` |
| 裁剪与媒体检查（4） | `batch_cut_video`、`cut_video`、`merge_videos`、`inspect_video_duration` |
| 转场与连续性（5） | `list_transition_presets`、`plan_transition_timeline`、`add_transition`、`score_cut_continuity`、`recommend_transition_for_cut` |
| 时间线与校验（4） | `validate_narration_timeline`、`build_edit_timeline_from_segments`、`align_narration_to_timeline`、`validate_timeline_constraints` |
| 音频与旁白（4） | `duck_background_audio`、`normalize_loudness`、`add_narration`、`add_narration_segments` |
| 字幕与导出（2） | `add_subtitles`、`export_video` |

## 本仓库的工程化改造

| 改造 | 内容与记录 |
|---|---|
| FastAPI 后端迁移 | 从手写 HTTP 路由迁移到 FastAPI；原始本地提交 `ac7a0f1`，代码已包含在 Vue 代码快照中 |
| Vue 3 工作台迁移 | 将 React 工作台迁移到 Vue 3，调整入口、组件和 Vite 配置；原始本地提交 `57e6e7c` |
| 视频分析时间映射 | 保存分析结果时映射到源视频时间轴，补充回归测试；[提交 `7dc778b`](https://github.com/lnzz21/auto-video-agent/commit/7dc778bad124ee676e19359eb6078ac2ca2459de) |
| 队列与独立 Worker | 本地工作区已新增 Redis 队列、Worker、PostgreSQL 与 Docker 配置，仍需收尾和验证 |

三阶段工作流、DAG 调度和恢复机制属于项目整体能力。现存 Git 历史中，这些能力已包含在初始完整快照内；本仓库后续改造可按上表及提交记录追溯。

## 本地运行

### 获取完整代码

默认 `main` 分支已整合完整项目代码、视频分析时间轴修复和项目说明：

```powershell
git clone --branch main https://github.com/lnzz21/auto-video-agent.git
cd auto-video-agent
```

### 运行前准备

- Python 3.10+，以及项目依赖环境。
- Node.js 与 npm，版本需满足所用 Vite 的要求。
- FFmpeg、FFprobe 可从运行环境定位到。
- 文本模型、视频模型与 TTS 服务配置。
- 字幕所需字体：当前独立字幕工具读取 `AlibabaPuHuiTi-3-55-Regular/AlibabaPuHuiTi-3-55-Regular.ttf`。

代码快照未包含字体、打包二进制及部分静态资源。历史 `requirements.txt` 存在编码混用，新环境安装前需先规范化依赖清单；核验情况见 [Git 与发布检查报告](docs/git-history.md)。

### 构建工作台

```powershell
cd app/frontend_src
npm ci
npm run build
cd ../..
```

生成的 `app/frontend/` 由后端提供静态页面。

### 配置与启动

在已有依赖环境中，启动后端：

```powershell
python script/run_backend.py --host 127.0.0.1 --port 8765
```

打开 [本地工作台](http://127.0.0.1:8765/ui/)，在设置中填写模型与 TTS 配置。运行根目录的 `.env` 是配置来源，可参考 [`.env.example`](.env.example)。

- 工作台：`http://127.0.0.1:8765/ui/`
- 接口文档：`http://127.0.0.1:8765/docs`
- 健康检查：`http://127.0.0.1:8765/health`

也可通过 CLI 提交任务：

```powershell
python script/agent.py "制作一条 60 秒校园宣传片，风格清新，带中文旁白和字幕"
```

运行目录可通过 `CRAYOTTER_RUNTIME_ROOT` 指定。后台任务使用按 job 隔离的工作区，恢复任务时保留原有检查点和有效产物。

## 当前版本边界与后续计划

- **单任务内并发**：已具备资源池、依赖和冲突键调度。
- **多个视频任务并发**：队列化改造仍在本地工作区；任务创建入口保留单任务限制，尚未完成多 Worker 端到端验证。
- **检索增强**：目前使用文本片段检索，后续可加入混合检索与重排。
- **输入与时间轴可靠性**：模型输出仍需格式、范围和时间坐标校验。
- **部署复现**：后续需规范化依赖编码、补齐必要资源，并验证干净环境部署。
- **实验目录**：`phase3_rl/` 为独立实验管线，不属于当前主应用的稳定交付能力。

## 目录导航

| 路径 | 职责 |
|---|---|
| `script/agent.py` | Agent 入口与任务运行 |
| `script/graph.py`、`script/workflow/` | 阶段编排、状态与路由 |
| `script/orchestration/` | 调度、资源、预算与产物管理 |
| `script/tools/` | 视频、音频、搜索、分析和导出工具 |
| `app/backend/` | FastAPI、任务管理与事件接口 |
| `app/frontend_src/` | Vue 3/Vite 工作台源码 |
| `tests/` | 调度、恢复、计划、媒体和接口相关测试 |
| `docs/` | 架构、素材源与开发记录 |
| `phase3_rl/` | 独立实验与烟雾验证管线 |

## 开发验证

按改动范围执行检查；真实素材平台和模型服务需要相应网络及配置。

```powershell
python -m unittest discover -s tests -v
```

前端改动后，从 `app/frontend_src/` 执行 `npm run build`。测试目录提供相关用例，测试结果以实际运行环境为准。

## 项目来源与许可证

基础视频 Agent 工作流来自 [Crayotter](https://github.com/idwts/Crayotter)。本仓库保留其版权声明和 [PolyForm Noncommercial License 1.0.0](LICENSE)。

原英文 README 已归档至 [docs/README.upstream.md](docs/README.upstream.md)，原中文说明保留在 [README_CN.md](README_CN.md)。其中的论文、演示、发布记录与性能数据属于原项目说明；本首页仅描述可从当前代码和改造记录核验的能力。
