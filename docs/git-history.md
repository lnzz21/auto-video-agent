# Git 提交、分支与主线整理记录

主线整理日期：**2026-10-28（Asia/Shanghai）**

## 当前主线状态

GitHub 默认 `main` 已整合完整项目代码、视频分析时间轴修复、新版首页 README 和本报告。仓库首页及默认克隆均以 `main` 为入口。

| 远程分支 | 当前内容 |
|---|---|
| [`main`](https://github.com/lnzz21/auto-video-agent/tree/main) | 主线合并提交；同时保留原占位提交 `eb87060` 和代码修复提交 `7dc778b` 的历史 |
| `feat/vue-frontend-code` | 原代码快照 `023ce4e`，已被主线包含 |
| `fix/video-analysis-reliability` | 时间轴修复 `7dc778b`，已被主线包含 |

本次主线合并的两个父提交分别为 `eb87060`、`7dc778b`，因此双方历史均可沿 `main` 追溯。远程三个分支合计可达 4 个提交；合并提交哈希以 GitHub `main` 的最新记录为准。

## 本地分支与发布范围

- 本地旧 `main` 的 `ac7a0f1` 开发历史保留为 `codex/main-before-code-import`。
- 本地新的 `main` 跟踪 `origin/main`；原 `feat/vue-frontend`、代码快照和修复分支保留。
- 原开发目录 `D:/Crayotter-main` 仍保留修复分支及未提交的后端、队列、部署和资源文件。
- 本次发布基线为已提交的 `7dc778b`，并加入 `README.md`、`docs/git-history.md` 和 `docs/README.upstream.md`。
- Redis、PostgreSQL、独立 Worker 和 Docker 的未完成改造继续保留在本地，功能状态仍按首页“进行中”描述。
- 本次是普通、保留历史的推送；原有功能分支继续作为历史参考。

## 整理前的历史快照

> 以下各节保留主线整理前的审计结果。表格中“main 仅有占位 README”和本地分支关系描述的是整理前状态；当前状态以上文为准。依赖编码、缺失资源和队列化收尾问题仍然存在。

核验日期：**2026-10-28（Asia/Shanghai）**  
仓库：[lnzz21/auto-video-agent](https://github.com/lnzz21/auto-video-agent)  
本地工作区：`D:/Crayotter-main`  
当前分支：`fix/video-analysis-reliability`

远程信息通过 `git ls-remote --heads origin` 与 `git fetch --prune origin` 核验。以下结论区分 GitHub 当前状态、本地历史及尚未提交的工作区内容。

## 1. 主要发现

1. GitHub 默认分支是 `main`，其提交 `eb87060` 仅有一份一行 README，内容为 `# auto-video-agent`。
2. 完整代码已经推送到 `feat/vue-frontend-code`，时间轴修复在其子分支 `fix/video-analysis-reliability`。
3. 本地 `main` 与远程 `main` 没有共同祖先，不能按普通的领先/落后提交数解释。
4. 本地早期开发链和代码专用快照也没有共同祖先。代码快照吸收了此前的 FastAPI/Vue 改造内容，但没有保留那条链上的父提交关系。
5. Redis、PostgreSQL、独立 Worker 和 Docker 改造仍是本地未提交内容。新首页将其标记为进行中。
6. 当前存在依赖编码及资源完整性问题，新环境部署仍需处理。

## 2. GitHub 远程分支

| 分支 | 远程提交 | 内容与关系 |
|---|---|---|
| `main` | `eb87060` | 默认分支；独立根提交；仅占位 README |
| `feat/vue-frontend-code` | `023ce4e` | 完整代码快照；独立根提交；包含 FastAPI 和 Vue 工作台 |
| `fix/video-analysis-reliability` | `7dc778b` | 以 `023ce4e` 为父提交，增加时间轴映射与回归测试 |

远程可达的提交合计 **3 个**。当前查询到的远程分支列表未包含 `feat/vue-frontend`。

分支链接：

- [main](https://github.com/lnzz21/auto-video-agent/tree/main)
- [feat/vue-frontend-code](https://github.com/lnzz21/auto-video-agent/tree/feat/vue-frontend-code)
- [fix/video-analysis-reliability](https://github.com/lnzz21/auto-video-agent/tree/fix/video-analysis-reliability)

## 3. 本地分支

| 本地分支 | 提交 | 上游与状态 |
|---|---|---|
| `main` | `ac7a0f1` | 未配置上游；与 `origin/main` 是不同历史 |
| `feat/vue-frontend` | `57e6e7c` | 未配置上游；继承本地 `main`；仅在本地可见 |
| `feat/vue-frontend-code` | `023ce4e` | 跟踪 `origin/feat/vue-frontend-code`，提交一致 |
| `fix/video-analysis-reliability` | `7dc778b` | 当前分支；跟踪对应远程分支，提交一致；工作区有未提交内容 |

“提交一致”只表示本地与远程分支指针相同，不表示工作区干净。

## 4. 提交时间线

以下按北京时间排列，包含本地所有分支可达的 **6 个提交**。

| 时间 | 提交 | 说明 | 当前可达范围 |
|---|---|---|---|
| 2026-09-05 14:49:00 | `eb87060` | Initial commit：创建占位 README | GitHub `main` |
| 2026-09-05 14:53:41 | `7ac3bcc` | Initial commit: Crayotter auto video agent：导入完整项目 | 本地早期历史 |
| 2026-09-05 15:07:46 | `ac7a0f1` | Migrate local backend to FastAPI | 本地 `main` / `feat/vue-frontend` |
| 2026-09-07 00:32:12 | `57e6e7c` | Migrate workbench frontend from React to Vue | 本地 `feat/vue-frontend` |
| 2026-09-07 01:13:59 | `023ce4e` | Initial code-only snapshot with Vue workbench | GitHub 代码分支及修复分支 |
| 2026-09-17 10:48:33 | `7dc778b` | fix(analysis): map proxy timestamps to source timeline | GitHub 修复分支 |

### 各条历史的实际关系

- 占位仓库历史：`eb87060`，独立根提交。
- 本地早期开发历史：`7ac3bcc → ac7a0f1 → 57e6e7c`。
- 已推送代码历史：`023ce4e → 7dc778b`。

上面三条历史的根不同。以下组合均没有共同祖先：

- 本地 `main` 与 `origin/main`。
- `origin/main` 与 `origin/feat/vue-frontend-code`。
- `feat/vue-frontend` 与 `origin/feat/vue-frontend-code`。

单独看到 `git rev-list --left-right --count` 的数字时，要结合共同祖先检查，避免误判为普通分叉。

## 5. 可追溯的工程化改造

### FastAPI 迁移：ac7a0f1

改动文件：

- `app/backend/server.py`
- `script/run_desktop.py`
- `requirements.txt`
- `requirements-desktop.txt`

将原有 HTTP 后端迁移为 FastAPI，并调整桌面运行适配和相关依赖。该提交保存在本地早期历史，其代码内容已进入之后的代码快照。

### Vue 迁移：57e6e7c

将 React 入口和组件迁移到 `App.vue` / `main.js`，调整 Vite、npm 依赖、Tailwind 配置和构建输出。该提交仅在本地早期历史可追溯；Vue 源码包含于远程 `023ce4e` 快照。

### 代码快照：023ce4e

重新建立代码专用根提交。与前一条本地 Vue 开发线相比，清除了视频、构建产物、字体、二进制及部分图像资源；核心后端和 Vue 源码延续。

因此，这份快照适合代码托管，但目前不能等同于资源齐全的发行包。

### 视频分析修复：7dc778b

修改 `script/tools/_shared.py`，新增 `tests/test_analysis_persistence.py`。

保存分析结果时，依据源视频与分析视频的时长比例映射时间范围，并保存时长与比例信息。测试覆盖“120 秒源视频 / 45 秒分析代理，9～15 秒映射为 24～40 秒”的情况。

该提交没有包含后续讨论过的全部语义解析治理，例如限制仅解析指定报告章节；介绍时应按实际修改范围描述。

## 6. 本地尚未提交的内容

### 已跟踪文件的修改

- `app/backend/runtime_manager.py`：接入可选 PostgreSQL、Redis 入队、独立 Worker 调用、事件持久化和跨进程取消检查等。
- `app/backend/server.py`：剪辑计划缺失时返回 404。

### 新增但尚未纳入 Git 的工程文件

- `app/backend/services/redis_queue.py`
- `app/backend/services/postgres_repository.py`
- `app/backend/worker.py`
- `script/run_backend_worker.py`
- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`
- `requirements-server.txt`
- `docs/deployment_10_users.md`

### 其他未跟踪内容

字体、FFmpeg/yt-dlp 等二进制、前端构建与图像资源、演示视频、网站资源、个人笔记和学习资料也存在于工作区。它们需要按用途和来源分别筛选，不能整体视作待发布项目代码。

本次另生成根目录首页、当前报告和原 README 归档，这些文档也需要在后续发布时选择性纳入提交。

## 7. 发布与部署检查

### 多任务并发尚未完成

`RuntimeManager.create_job()` 仍在检测到其他 `queued/running` 任务时拒绝创建新任务。因此，虽然存在 Redis 队列和 Worker 基础代码，当前入口仍会限制多任务接入。

需进一步处理：

- 在队列模式下明确任务接入与执行容量的区别。
- 验证两个任务入队、两个 Worker 执行及状态查询。
- 验证取消、恢复、Worker 异常退出和事件刷新。
- 为领取后的任务增加明确的确认、失败回收与重复执行防护机制。
- 评估多个 Worker 下的全局资源配额；当前阶段内资源池主要按执行进程管理。

“10 人规模”是设计目标，当前记录与代码不足以证明对应的吞吐量、稳定性或压测指标。

### 依赖清单编码

`requirements.txt` 当前为 3040 字节，含 1489 个 NUL 字节，开头出现重复 UTF-16 BOM；与早期提交比较，还存在后续追加的不同编码内容。

新环境安装前应规范化为 UTF-8，检查各依赖行，再执行依赖解析及安装验证。本次文档整理保留了原依赖文件。

### 必要资源未进入代码快照

当前分支未跟踪下列目录：

- `AlibabaPuHuiTi-3-55-Regular/`
- `script/dep/`
- `app/frontend/`
- `app/frontend_src/public/`
- `app/frontend_src/src/assets/`

其中前端静态构建可从源码生成；字体、媒体二进制和其他资源需要提供明确获取方式，并核对其分发许可。新首页没有引用这些未发布的图片、视频或徽标，以避免远程显示损坏。

### 首页与来源

原根 README 含原项目论文、演示、发布记录及性能数据。新的首页将其放回项目来源语境，保留 LICENSE，并归档原英文说明，避免把原项目成果描述为本仓库新增实绩。

## 8. 建议的整理与发布顺序

以下为建议，不是已执行的远程操作。

1. **文档提交**：纳入 `README.md`、`docs/git-history.md` 和 `docs/README.upstream.md`。
2. **安装修复提交**：单独规范化依赖编码，并补齐必要资源的获取说明。
3. **队列功能提交**：按完整目标整理 RuntimeManager、Redis、Worker、PostgreSQL 及相关验证。
4. **部署提交**：整理 Docker、服务依赖、配置示例及部署文档。
5. **默认分支整理**：以完整代码历史为交付内容，在独立整理分支中处理其与占位 `main` 的无共同祖先问题，核对冲突和资源后再发布。

可采用保留双方历史的合并方案，避免强制覆盖远程历史；由于双方没有共同祖先，需要明确处理这一点，不能直接当作普通功能分支合并。

如果短期只需要让访客看到完整代码，可先评估将完整代码分支设为 GitHub 默认分支；长期仍建议建立名称与职责清晰的稳定主线。

不要仅将新 README 推送到占位 `main` 而不带入代码，否则首页的相对源码链接与运行说明仍无法对应仓库内容。
