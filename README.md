# HF Papers Archive

自动抓取 Hugging Face `papers/date/<YYYY-MM-DD>` 页面，归档每篇论文信息（含 AI-generated summary 的中英版本），并生成可部署到 GitHub Pages 的静态站点。

当前版本：`v0.1`

## 功能

- 按日期抓取：`https://huggingface.co/papers/date/YYYY-MM-DD`
- 单篇字段归档（JSON）：
  - `title`
  - `authors`
  - `abstract`（从 HF 论文页抽取）
  - `summary_en`
  - `summary_zh`
  - `hf_url`
  - `arxiv_url`
  - `arxiv_pdf_url`（由 arXiv abs 链接自动转换）
  - `github_url`（若 HF 页面提供）
  - `upvotes`（HF 页面点赞数）
  - `fetched_at`
- 翻译可插拔：
  - 默认 `dummy`（无密钥也能跑完整流程）
  - 可选 `openrouter`（设置 `OPENROUTER_API_KEY` 后启用）
  - OpenRouter 默认模型：`moonshotai/kimi-k2.5`（可通过环境变量覆盖）
- 索引生成：
  - `data/index.json`
  - `data/search_index.json`
  - `data/dates/<date>.json`
- 静态站点（Next.js 导出）：
  - 顶部「今日论文总览」AI 摘要（可折叠，默认展开）
  - 日期分组列表
  - 详情页
  - 全文搜索（lunr）
  - 中英 summary 切换
  - Abstract 折叠/展开
  - 默认按 upvotes 降序展示

## 项目结构

```text
hf-papers-archive/
  scripts/
    fetch_daily.py
    translate.py
    build_index.py
  data/
    papers/
    dates/
    index.json
    search_index.json
  site/
    app/
    components/
    lib/
    scripts/sync-data.mjs
    next.config.mjs
    package.json
  .github/workflows/
    daily.yml
  requirements.txt
  README.md
```

## 本地运行

### 1) 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

```bash
cd site
npm install
cd ..
```

### 2) 抓取某一天

```bash
python3 scripts/fetch_daily.py --date 2026-02-16
```

输出示例：`data/papers/2026-02-16__2602.10388.json`

增量抓取（已存在完整 JSON 则跳过）：

```bash
python3 scripts/fetch_daily.py --date 2026-02-16 --skip-existing-complete
```

### 3) 生成中文摘要

`translate.py` 现在支持：当论文缺少 `summary_en` 时，自动基于 `abstract` 先生成英文摘要，再翻译为 `summary_zh`（若 `abstract` 不可用则跳过）。

默认（无密钥）：

```bash
python3 scripts/translate.py --provider dummy
```

自动模式（有 `OPENROUTER_API_KEY` 则调用 OpenRouter，无则回退 dummy）：

```bash
export OPENROUTER_API_KEY=your_key
export OPENROUTER_MODEL=moonshotai/kimi-k2.5
python3 scripts/translate.py --provider auto
```

显式指定 OpenRouter：

```bash
python3 scripts/translate.py --provider openrouter
```

只翻译指定日期（推荐给自动任务）：

```bash
python3 scripts/translate.py --provider auto --date 2026-02-16
```

切换其他 OpenRouter 模型（无需改代码）：

```bash
python3 scripts/translate.py --provider openrouter --model anthropic/claude-3.5-sonnet
```

### 4) 构建索引

```bash
python3 scripts/build_index.py
```

若配置 `OPENROUTER_API_KEY`，会在构建索引时额外生成“今日论文总览”AI 摘要（写入 `data/index.json`）。

### 5) 构建静态站点

```bash
npm run build --prefix site
```

构建产物目录：`site/out/`

### 一键执行（本地）

```bash
python3 scripts/fetch_daily.py --date 2026-02-16 \
  && python3 scripts/translate.py --provider auto \
  && python3 scripts/build_index.py \
  && npm run build --prefix site
```

## 数据格式

单篇 JSON（`data/papers/YYYY-MM-DD__<paper_id>.json`）示例：

```json
{
  "date": "2026-02-16",
  "paper_id": "2602.10388",
  "title": "Paper Title",
  "authors": ["Author A", "Author B"],
  "abstract": "Paper abstract text ...",
  "summary_en": "HF AI-generated summary ...",
  "summary_zh": "中文翻译...",
  "hf_url": "https://huggingface.co/papers/2602.10388",
  "arxiv_url": "https://arxiv.org/abs/2602.10388",
  "arxiv_pdf_url": "https://arxiv.org/pdf/2602.10388",
  "github_url": "https://github.com/org/repo",
  "upvotes": 202,
  "fetched_at": "2026-02-17T01:23:45.678901+00:00"
}
```

索引中的「今日论文总览」字段（`data/index.json`）示例：

```json
{
  "daily_summary": {
    "date": "2026-02-16",
    "content": "今日论文整体聚焦于...",
    "source": "openrouter",
    "model": "moonshotai/kimi-k2.5",
    "generated_at": "2026-02-17T08:47:39.574870+00:00"
  }
}
```

## GitHub Actions（每日自动更新）

工作流：`.github/workflows/daily.yml`

触发方式：

- 定时：每天 GMT+8 23:00（即 UTC 15:00）
- 手动：`workflow_dispatch`

流程：

1. Checkout
2. 安装 Python 依赖
3. 计算目标日期（可选 CST / UTC / JST）
4. `fetch_daily.py`
5. `translate.py`
6. `build_index.py`
7. 若 `data/` 有变化则自动 commit & push
8. 构建 Next.js 静态站点
9. 部署到 GitHub Pages

### 手动运行示例

在 GitHub Actions 页面运行 `Daily HF Papers Archive`：

- `date`: `2026-02-16`
- `timezone`: `CST`
- `translator`: `dummy`（或 `openrouter`）

### Pages 配置

- 仓库 Settings -> Pages -> Build and deployment -> Source 选择 `GitHub Actions`
- 默认会自动推断 project pages basePath；必要时可设置 `NEXT_BASE_PATH`

## 注意事项

- 抓取器带随机限速（默认 0.5~1.5s）和最多 3 次重试。
- 页面结构可能变化，脚本采用 DOM 容错解析，字段可能为空但流程不应崩溃。
- `summary_en` 仅在页面存在 AI-generated summary 时写入；否则会留空，避免写入无效文案。
- 若要真实翻译，请在仓库 Secrets 中配置：
  - `OPENROUTER_API_KEY`
  - 可选 `OPENROUTER_MODEL`（默认 `moonshotai/kimi-k2.5`）
  - 可选 `OPENROUTER_SUMMARY_MODEL`（控制“今日论文总览”模型，默认跟随 `OPENROUTER_MODEL`）

## v0.1 上传与部署清单

1. 创建 GitHub 仓库（空仓库，不要初始化 README）。
2. 本地设置远端并推送：
   ```bash
   git add .
   git commit -m "release: v0.1"
   git branch -M main
   git remote add origin <your_repo_url>
   git push -u origin main
   ```
3. 在 GitHub 仓库 `Settings -> Secrets and variables -> Actions` 添加：
   - `OPENROUTER_API_KEY`（必需，若你要真实翻译/AI 总览）
   - `OPENROUTER_MODEL`（可选）
   - `OPENROUTER_SUMMARY_MODEL`（可选）
4. 在 `Settings -> Actions -> General -> Workflow permissions` 里选择 `Read and write permissions`（用于自动提交 `data/` 更新）。
5. 在 GitHub 仓库 `Settings -> Pages` 里将 Source 设为 `GitHub Actions`。
6. 在 Actions 页面手动运行一次 `Daily HF Papers Archive`（`workflow_dispatch`）做首轮部署验证。
