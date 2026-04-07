# SEO / GEO Article Writer

<div align="center">

### Open-source AI writing workflow for SEO and GEO content

从关键词和品牌信息出发，自动生成更适合搜索引擎与 AI 引用场景的文章草稿。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-black?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[Live Preview](https://www.idtcpack.com/) · [Quick Start](#quick-start) · [API](#api) · [Roadmap](#roadmap)

</div>

---

## Why This Project

很多 AI 写作工具只能“生成文章”，但很难真正兼顾两件事：

- `SEO`：关键词布局、标题结构、Meta 规范、FAQ、可读性
- `GEO`：answer-first、可引用性、实体清晰度、references、trust signals

这个项目的目标不是只做一个简单写稿器，而是做一个适合开源和二次开发的基础框架：

- 输入 `类别（SEO / GEO）`
- 输入 `一个或多个关键词`
- 输入 `品牌 / 产品 / 业务信息`
- 生成针对不同内容目标的文章草稿
- 生成 1 张封面图和 2-3 张正文配图
- 对 `category + keyword + info` 做缓存复用
- 通过 API 提交任务并异步获取结果

---

## Preview

- Live Preview: [https://www.idtcpack.com/](https://www.idtcpack.com/)
- Local Demo: `http://127.0.0.1:8028`

---

## Features

- 支持 `SEO` 和 `GEO` 两种不同写作模式
- 支持多个关键词批量提交
- 支持异步任务创建与轮询查询
- 支持单关键词缓存，避免重复生成
- 支持 Azure OpenAI 文生图
- 自动为每篇文章生成 `1` 张封面和 `2-3` 张正文配图
- 自动把图片注入最终 HTML 预览
- 内置 Web Demo 页面，方便直接演示
- 默认支持 `mock mode`，不开 API Key 也能跑通流程
- 可切换到 OpenAI-compatible 接口，方便接 OpenAI / OpenRouter / 自建兼容网关

---

## Writing Logic

### SEO Mode

SEO 模式参考了原有 PHP 三段式生成流程，以及内容培训文档中的写作规范：

- 先做策略分析：搜索意图、受众、H1、Meta、长尾词、FAQ、内容骨架
- 再生成正文：`H1 -> Intro -> H2/H3 -> Conclusion -> FAQ`
- 最后做人类化润色：减少 AI 腔，增强具体性和自然度

核心规则包括：

- `Meta Title <= 60`
- `Meta Description <= 160`
- 页面只保留一个 H1
- 主关键词优先出现在 `Title / Description / H1 / 首段 / 结尾`
- 段落尽量短，结构清晰，FAQ 2-4 个

### GEO Mode

GEO 模式参考了 [site-geo](https://github.com/daogeshifu/site-geo) 的 AI-ready 信号设计思想，重点不是“更像 SEO”，而是“更容易被 AI 理解、提取、引用”。

核心方向包括：

- answer-first
- TL;DR
- FAQ
- references / inline citations
- quantified proof blocks
- entity clarity
- update log / trust signals

这意味着 GEO 文章更强调：

- 第一屏直接回答问题
- 标题和段落更利于抽取
- 论点尽量有证据感和可引用性
- 品牌 / 产品 / 实体信息保持一致

---

## Architecture

```text
.
├── demo.py                     # 单文件 demo console 页面
├── app
│   └── main.py                 # Flask app 启动入口
├── requirements.txt
├── start.sh                    # 启动脚本
├── seo_geo_writer
│   ├── web.py                  # Web 页面 + API 路由
│   ├── task_service.py         # 异步任务管理
│   ├── cache_service.py        # category + keyword + info 缓存
│   ├── image_service.py        # Azure / mock 图片生成
│   ├── writer_service.py       # SEO / GEO 写作总流程
│   ├── prompt_builder.py       # 两套 prompt 逻辑
│   ├── llm_client.py           # OpenAI-compatible client
│   ├── config.py               # 配置
│   └── utils.py                # 通用工具
├── templates
│   └── index.html              # Demo 页面
├── static
│   └── style.css               # Demo 样式
└── tests
    ├── test_api.py
    └── test_cache_service.py
```

---

## Quick Start

### 1. Clone

```bash
git clone <your-repo-url>
cd site-seo-geo-article
```

### 2. Create virtualenv

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure env

```bash
cp .env.example .env
```

### 5. Run

```bash
./start.sh
```

默认会：

- 自动创建并激活 `.venv`
- 自动安装依赖
- 自动加载 `.env`
- 检查目标端口占用
- 若端口冲突则自动切到下一个可用端口

后台模式：

```bash
IS_PROD=Y ./start.sh
```

Open:

```text
http://127.0.0.1:8028
```

---

## Environment Variables

| Name | Default | Description |
|---|---|---|
| `FLASK_HOST` | `0.0.0.0` | Flask host |
| `FLASK_PORT` | `8028` | Flask port |
| `FLASK_DEBUG` | `true` | Debug mode |
| `APP_DATA_DIR` | `./data` | Data directory |
| `MAX_WORKERS` | `2` | Async worker count |
| `LLM_MOCK_MODE` | `true` | Use local mock output instead of real LLM |
| `OPENAI_API_KEY` | empty | OpenAI-compatible API key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | API base URL |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Model name |
| `OPENAI_REQUEST_TIMEOUT` | `90` | Request timeout |
| `AZURE_IMAGE_API_URL` | empty | Full Azure image generation URL |
| `AZURE_IMAGE_API_KEY` | empty | Azure image generation key |
| `AZURE_IMAGE_ENDPOINT` | empty | Optional Azure endpoint base URL |
| `AZURE_IMAGE_DEPLOYMENT` | `gpt-image-1.5` | Azure deployment name |
| `AZURE_IMAGE_API_VERSION` | `2025-04-01-preview` | Azure image API version |
| `AZURE_IMAGE_SIZE` | `1536x1024` | Generated image size |
| `AZURE_IMAGE_QUALITY` | `medium` | Image quality |
| `AZURE_IMAGE_OUTPUT_FORMAT` | `png` | Output format |
| `ARTICLE_CONTENT_IMAGE_COUNT` | `3` | Body image count per article |
| `IS_PROD` | `N` | Start in background when set to `Y` |
| `AUTO_KILL_PORT` | `N` | Kill the requested port instead of auto-switching |

If you keep `LLM_MOCK_MODE=true`, the whole workflow still works for demo and development.

---

## API

统一返回格式：

```json
{ "success": true, "data": {} }
{ "success": false, "message": "..." }
```

### Create Task

```bash
curl -X POST http://127.0.0.1:8028/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "category": "seo",
    "keywords": ["portable charger on plane", "tsa power bank rules"],
    "info": "Brand: VoltGo. Product: 20000mAh portable charger for travel.",
    "language": "English",
    "generate_images": true
  }'
```

Response:

```json
{
  "success": true,
  "data": {
    "task_id": "4ce7c5807d8b4c4d91538e1b10fd9556",
    "status": "queued"
  }
}
```

### Get Task

```bash
curl http://127.0.0.1:8028/api/tasks/4ce7c5807d8b4c4d91538e1b10fd9556
```

Response:

```json
{
  "success": true,
  "data": {
    "task_id": "4ce7c5807d8b4c4d91538e1b10fd9556",
    "status": "completed",
    "progress": {
      "total": 2,
      "completed": 2,
      "failed": 0,
      "cached": 1
    },
    "items": [
      {
        "keyword": "portable charger on plane",
        "status": "completed",
        "cache_hit": true,
        "article": {
          "title": "...",
          "meta_title": "...",
          "meta_description": "...",
          "html": "...",
          "generation_mode": "llm",
          "image_generation_mode": "azure",
          "images": [
            {
              "role": "cover",
              "url": "/generated/<asset_namespace>/01-cover-portable-charger.png"
            }
          ]
        }
      }
    ]
  }
}
```

### Health Check

```bash
curl http://127.0.0.1:5000/api/health
```

---

## Cache Strategy

缓存粒度是单关键词，而不是整个批次任务。

```text
cache_key = sha256(category + normalized_keyword + normalized_info)
```

这意味着：

- 多关键词任务会拆成多个独立缓存单元
- 如果 `category + keyword + info` 完全一致，会直接返回缓存结果
- 相同词但品牌信息不同，会视为不同生成结果

---

## Web Demo

项目内置了一个更接近 `site-geo` 风格的单文件 console 页面，核心在 `demo.py`，支持：

- 选择 `SEO / GEO`
- 输入多关键词
- 输入品牌 / 产品信息
- 开关控制是否生成图片
- 提交任务
- 轮询任务状态
- 查看缓存命中情况
- 预览最终 HTML
- 预览封面图与正文配图
- 直接查看 API 调用示例和启动命令

---

## Tests

```bash
.venv/bin/pytest
```

当前测试覆盖：

- API 创建任务与查询结果
- 缓存命中逻辑

---

## Use Cases

- 开源 AI 写作项目原型
- SEO 内容自动生成实验
- GEO / AI Search 内容策略验证
- 品牌站 / 产品站内容生产工具
- 批量关键词内容工作流的基础服务

---

## Roadmap

- [ ] 支持 Markdown / JSON / HTML 多输出格式
- [ ] 支持数据库存储任务和缓存
- [ ] 支持 Redis / Celery / RQ 异步队列
- [ ] 支持文章导出到 CMS
- [ ] 支持多语言模板
- [ ] 支持文章质量评分和二次改写
- [ ] 支持 Docker 部署

---

## Acknowledgements

- 原始业务逻辑灵感来自旧版 PHP 写作流程
- SEO 规范参考内部培训文档《内容培训0313-杨玉齐》
- GEO 方向参考 [daogeshifu/site-geo](https://github.com/daogeshifu/site-geo)

---

## License

MIT
