# HF Papers Archive

自动抓取 Hugging Face `papers/date/<YYYY-MM-DD>` 页面，归档每篇论文信息（含 AI-generated summary 的中英版本），并生成可部署到 GitHub Pages 的静态站点。

## 功能

- 按日期抓取：`https://huggingface.co/papers/date/YYYY-MM-DD`
- 单篇字段归档（JSON）：
  - `title`
  - `authors`
  - `institutions`
  - `institution_source` (`hf` / `arxiv` / `none`)
  - `summary_en`
  - `summary_zh`
  - `hf_url`
  - `arxiv_url`
  - `fetched_at`
- 机构提取策略：
  - 优先 Hugging Face 页面
  - fallback 到 arXiv (`/html/<id>` 和 `/abs/<id>`) 的机构线索
  - 不可得则留空并标注 `institution_source=none`
- 翻译可插拔：
  - 默认 `dummy`（无密钥也能跑完整流程）
  - 可选 `openrouter`（设置 `OPENROUTER_API_KEY` 后启用）
  - OpenRouter 默认模型：`moonshotai/kimi-k2.5`（可通过环境变量覆盖）
- 索引生成：
  - `data/index.json`
  - `data/search_index.json`
  - `data/dates/<date>.json`
- 静态站点（Next.js 导出）：
  - 日期分组列表
  - 详情页
  - 全文搜索（lunr）
  - 中英 summary 切换

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

### 3) 生成中文摘要

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

切换其他 OpenRouter 模型（无需改代码）：

```bash
python3 scripts/translate.py --provider openrouter --model anthropic/claude-3.5-sonnet
```

### 4) 构建索引

```bash
python3 scripts/build_index.py
```

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
  "institutions": ["University X", "UGA"],
  "institution_source": "arxiv",
  "summary_en": "HF AI-generated summary ...",
  "summary_zh": "中文翻译...",
  "hf_url": "https://huggingface.co/papers/2602.10388",
  "arxiv_url": "https://arxiv.org/abs/2602.10388",
  "fetched_at": "2026-02-17T01:23:45.678901+00:00"
}
```

## GitHub Actions（每日自动更新）

工作流：`.github/workflows/daily.yml`

触发方式：

- 定时：每天 UTC 01:20
- 手动：`workflow_dispatch`

流程：

1. Checkout
2. 安装 Python 依赖
3. 计算目标日期（可选 UTC / JST）
4. `fetch_daily.py`
5. `translate.py`
6. `build_index.py`
7. 若 `data/` 有变化则自动 commit & push
8. 构建 Next.js 静态站点
9. 部署到 GitHub Pages

### 手动运行示例

在 GitHub Actions 页面运行 `Daily HF Papers Archive`：

- `date`: `2026-02-16`
- `timezone`: `UTC`
- `translator`: `dummy`（或 `openrouter`）

### Pages 配置

- 仓库 Settings -> Pages -> Build and deployment -> Source 选择 `GitHub Actions`
- 默认会自动推断 project pages basePath；必要时可设置 `NEXT_BASE_PATH`

## 注意事项

- 抓取器带随机限速（默认 0.5~1.5s）和最多 3 次重试。
- 页面结构可能变化，脚本采用 DOM 容错解析，字段可能为空但流程不应崩溃。
- 若要真实翻译，请在仓库 Secrets 中配置：
  - `OPENROUTER_API_KEY`
  - 可选 `OPENROUTER_MODEL`（默认 `moonshotai/kimi-k2.5`）
