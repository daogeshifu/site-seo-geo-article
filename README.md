# SEO / GEO Article Writer

<div align="center">

### Open-source AI writing workflow for SEO and GEO content

从关键词和品牌信息出发，自动生成更适合搜索引擎与 AI 引用场景的文章草稿。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
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
- 支持将生成图片自动上传到阿里云 OSS
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
├── app
│   ├── api
│   │   ├── routes.py           # API 路由
│   │   └── schemas.py          # API schema
│   ├── core
│   │   ├── config.py           # 配置
│   │   ├── factory.py          # FastAPI app 组装
│   │   └── runtime.py          # 共享服务初始化
│   ├── services
│   │   ├── image_service.py    # 图片服务
│   │   ├── prompt_builder.py   # Prompt 服务
│   │   ├── writer_service.py   # 写作编排
│   │   ├── task_service.py     # 异步任务服务
│   │   ├── cache_service.py    # 缓存服务
│   │   └── llm_client.py       # LLM 客户端
│   ├── utils
│   │   └── common.py           # 通用工具
│   ├── web
│   │   ├── routes.py           # Demo 页面路由
│   │   ├── context.py          # Demo 页面上下文
│   │   ├── templates/demo/index.html
│   │   └── static/demo/*
│   └── main.py                 # FastAPI app 启动入口
├── requirements.txt
├── Dockerfile                  # Docker image build file
├── docker-compose.yml          # Docker Compose deployment
├── .env.docker.example         # Docker environment example
├── start.sh                    # 启动脚本
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

### 6. Docker Deploy

```bash
cp .env.docker.example .env.docker
docker compose --env-file .env.docker up -d --build
```

默认会：

- 启动 `app` 和 `mysql` 两个容器
- 自动把本地 `./data` 挂载到容器内 `/app/data`
- 自动等待 MySQL 健康后再启动 FastAPI
- 自动把任务和结果持久化到 Compose 内置 MySQL

Open:

```text
http://127.0.0.1:8028
```

常用命令：

```bash
docker compose --env-file .env.docker logs -f app
docker compose --env-file .env.docker down
docker compose --env-file .env.docker down -v
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
| `ALIYUN_OSS_ACCESS_KEY_ID` | empty | Aliyun OSS AccessKey ID |
| `ALIYUN_OSS_ACCESS_KEY_SECRET` | empty | Aliyun OSS AccessKey Secret |
| `ALIYUN_OSS_ENDPOINT` | empty | Aliyun OSS endpoint, such as `https://oss-cn-beijing.aliyuncs.com` |
| `ALIYUN_OSS_BUCKET` | empty | Aliyun OSS bucket name |
| `ALIYUN_OSS_PUBLIC_BASE_URL` | empty | Optional public/custom domain base URL; if empty, private buckets use signed URLs |
| `ALIYUN_OSS_PREFIX` | `articles` | Object prefix used for uploaded images |
| `ALIYUN_OSS_URL_EXPIRE_SECONDS` | `86400` | Expiration seconds for signed OSS URLs |
| `DEFAULT_CONTENT_IMAGE_COUNT` | `3` | Demo default for body image count |
| `NORMAL_ACCESS_KEY` | empty | Standard access key used to exchange a bearer token |
| `VIP_ACCESS_KEY` | empty | VIP access key used to exchange a bearer token |
| `TOKEN_SIGNING_SECRET` | empty | Secret used to sign exchanged bearer tokens |
| `TOKEN_TTL_SECONDS` | `86400` | Bearer token lifetime in seconds |
| `MYSQL_HOST` | empty | MySQL host; when empty, uses in-memory task storage |
| `MYSQL_PORT` | `3306` | MySQL port |
| `MYSQL_USER` | empty | MySQL username |
| `MYSQL_PASSWORD` | empty | MySQL password |
| `MYSQL_DATABASE` | empty | MySQL database name; falls back to `MYSQL_USER` when empty |
| `MYSQL_CHARSET` | `utf8mb4` | MySQL charset |
| `MYSQL_CONNECT_TIMEOUT` | `10` | MySQL connection timeout seconds |
| `MYSQL_READ_TIMEOUT` | `20` | MySQL read timeout seconds |
| `MYSQL_WRITE_TIMEOUT` | `20` | MySQL write timeout seconds |
| `MYSQL_RETRY_COUNT` | `3` | Retry count for transient MySQL connection errors |
| `MYSQL_RETRY_DELAY_SECONDS` | `0.6` | Delay between MySQL retries |
| `MYSQL_POOL_SIZE` | `8` | MySQL connection pool size |
| `MYSQL_FALLBACK_TO_MEMORY` | `false` | Fall back to in-memory task storage when MySQL init fails |
| `IS_PROD` | `N` | Start in background when set to `Y` |
| `AUTO_KILL_PORT` | `N` | Kill the requested port instead of auto-switching |

If you keep `LLM_MOCK_MODE=true`, the whole workflow still works for demo and development.

## Deployment

### Local Script

适合本机开发、调试和快速预览：

```bash
./start.sh
```

### Docker Compose

适合标准化部署、团队协作和服务器环境：

```bash
cp .env.docker.example .env.docker
docker compose --env-file .env.docker up -d --build
```

说明：

- `app` 容器运行 FastAPI + Uvicorn
- `mysql` 容器提供任务元数据和文章结果存储
- 本地 `data/` 会映射到容器里的 `/app/data`
- 如果你已有外部 MySQL，可以在 `.env.docker` 里改 `MYSQL_HOST`，并从 `docker-compose.yml` 中移除 `mysql` 服务

镜像与编排文件：

- [Dockerfile](/Users/berry-zhang/workspace/site-seo-geo-article/Dockerfile)
- [docker-compose.yml](/Users/berry-zhang/workspace/site-seo-geo-article/docker-compose.yml)
- [.env.docker.example](/Users/berry-zhang/workspace/site-seo-geo-article/.env.docker.example)

---

## API

统一返回格式：

```json
{ "success": true, "data": {} }
{ "success": false, "message": "..." }
```

### Exchange Token

```bash
curl -X POST http://127.0.0.1:8028/api/token \
  -H "Content-Type: application/json" \
  -d '{"access_key":"YOUR_ACCESS_KEY"}'
```

### Create Task

```bash
curl -X POST http://127.0.0.1:8028/api/tasks \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "category": "seo",
    "keyword": "portable charger on plane",
    "info": "Brand: VoltGo. Product: 20000mAh portable charger for travel.",
    "language": "English",
    "word_limit": 1200,
    "include_cover": 1,
    "content_image_count": 2
  }'
```

Response:

```json
{
  "success": true,
  "data": {
    "task_id": 248,
    "status": "queued"
  }
}
```

### Get Task

```bash
curl http://127.0.0.1:8028/api/tasks/248 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:

```json
{
  "success": true,
  "data": {
    "task_id": 248,
    "category": "seo",
    "keyword": "portable charger on plane",
    "status": "completed",
    "cache_hit": true,
    "progress": {
      "total": 1,
      "completed": 1,
      "failed": 0,
      "cached": 1
    },
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
          "url": "data:image/png;base64,..."
        }
      ]
    }
  }
}
```

任务元数据和最终文章结果现在分别持久化到 MySQL 的 `article_tasks` 与 `article_task_results` 表；文件缓存按 `category + keyword + info + word_limit` 维度保留在本地 `data/cache/` 下。

---

## Cache Strategy

缓存粒度是单关键词。

```text
cache_key = sha256(category + normalized_keyword + normalized_info + word_limit)
```

这意味着：

- 每次任务只处理一个关键词
- 如果 `category + keyword + info + word_limit` 完全一致，会直接返回缓存结果
- 相同词但品牌信息不同，会视为不同生成结果

---

## Web Demo

项目内置了一个更接近 `site-geo` 风格的 FastAPI 模板 console 页面，由 `app/web/templates/` + `app/web/static/` 资源驱动，支持：

- 选择 `SEO / GEO`
- 输入单个关键词
- 输入品牌 / 产品信息
- 先用 access key 兑换 1 天 bearer token
- 控制封面图开关和正文图数量 `0-3`
- 提交任务
- 轮询任务状态
- 查看缓存命中情况
- 预览最终 HTML
- 预览封面图与正文配图
- 直接查看 API 调用示例和启动命令

MySQL 初始化 SQL 文件位于 [database/mysql_schema.sql](/Users/berry-zhang/workspace/site-seo-geo-article/database/mysql_schema.sql)，可以直接执行它来创建数据库和两张核心表。模板版本位于 [database/mysql_schema.template.sql](/Users/berry-zhang/workspace/site-seo-geo-article/database/mysql_schema.template.sql)，程序启动时会用它自动建表。

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
