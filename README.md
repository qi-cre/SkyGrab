# SkyGrab 🛰️

**Aggressive multi-source satellite data harvester with a modern TUI.**

SkyGrab 是一个激进的多线程卫星数据下载器。它将每个文件切分为固定大小的块，
用线程池并行拉取，通过全局令牌桶限速、块级断点续传，尽可能压满带宽而不触发
服务端限流。支持 EUMETSAT Data Store 与 NOAA AWS NODD 公开桶，下载得到的
产品可直接交给 [SatDump](https://github.com/satdump/satdump) 解码。

---

## ✨ 特性

- **分块并发** — 每个文件切分为 8 MB 块（可调），由 32 线程并行拉取
- **全局速率控制** — 令牌桶在全部线程间共享，避免打挂服务端
- **块级断点续传** — 中断后重新运行自动跳过已完成块
- **双数据源** — EUMETSAT Data Store + NOAA AWS NODD 公开桶
- **实时 TUI** — 每个产品的进度、速度、活跃线程数一目了然
- **指数退避重试** — 块级独立重试，单块失败不影响其他块
- **零配置 NOAA 访问** — 公开桶匿名访问，无需 AWS 账号
- **并行偏移写入** — 使用 `os.pwrite` 避免多线程文件指针竞争

---

## 📦 安装

### 从源码

    git clone https://github.com/kase/skygrab.git
    cd skygrab
    pip install -e .

### 开发模式

    pip install -e '.[dev]'

### 可选依赖

AWS Ground Station pcap 拉取（需 boto3）：

    pip install -e '.[ground]'

### 依赖

- Python >= 3.10
- textual >= 0.58
- requests >= 2.31
- urllib3 >= 2.0

---

## 🚀 快速开始

### 启动 TUI

NOAA 模式（无需鉴权）：

    skygrab --source noaa

EUMETSAT 模式（需 API key）：

    export EUMETSAT_API_KEY="your_key_here"
    skygrab

也可以直接：

    python -m skygrab

### TUI 操作流程

1. 顶栏 `Source` 选择 **EUMETSAT** 或 **NOAA AWS**
2. 填入检索条件
3. 按 `s` 或点 **Search**
4. 在左侧列表勾选要下载的产品（空格勾选）
5. 按 `d` 或点 **Download**
6. 按 `c` 取消，`q` 退出

### 检索条件说明

**EUMETSAT 模式**：

- `Collection` — 集合 ID，如 `EO:EUM:DAT:MSG:HRSEVIRI`
- `BBox` — 地理范围，格式 `minLon,minLat,maxLon,maxLat`
- `Start` / `End` — ISO 8601 时间，如 `2025-01-01T00:00:00Z`
- `Limit` — 返回结果条数上限

**NOAA 模式**：

- `Sat` — 卫星代号：`goes16` / `goes17` / `goes18` / `goes19` / `n20` / `n21` / `snpp`
- `Prod` — 产品路径，如 `ABI-L1b-RadF-Reproc`
- `YYYY` / `DDD` / `HH` — 年份 / 年积日 / 小时

---

## 🛰️ 支持的数据源

| 源 | 数据 | 鉴权 | 备注 |
|---|---|---|---|
| EUMETSAT Data Store | MSG、Metop、Sentinel-3 等 | API key | 需在 [data.eumetsat.int](https://data.eumetsat.int) 注册 |
| NOAA AWS NODD（公开） | GOES-16/17/18/19、NOAA-20/21、Suomi-NPP | 无 | 匿名访问 S3 公开桶 |
| AWS Ground Station（私有） | 原始 IQ 采样（pcap） | AWS 凭证 | 需已购 contact，数据在用户 bucket |

### NOAA 公开桶对照表

| 卫星 | S3 Bucket |
|---|---|
| GOES-16 | `noaa-goes16` |
| GOES-17 | `noaa-goes17` |
| GOES-18 | `noaa-goes18` |
| GOES-19 | `noaa-goes19` |
| NOAA-20 | `noaa-nesdis-n20-pds` |
| NOAA-21 | `noaa-nesdis-n21-pds` |
| Suomi-NPP | `noaa-nesdis-snpp-pds` |

> ⚠️ **NOAA 公开桶不是 baseband 源**：其中的 `.nc` 文件是已定标的产品，
> SatDump 通过内部 netCDF reader 读取，不走 baseband 解码管线。真正的
> baseband（IQ）需通过 AWS Ground Station 获取，属付费服务。

---

## ⚙️ 命令行参数

    usage: skygrab [-h] [--source {eumetsat,noaa}] [-o PATH] [-w N]
                   [--chunk-mb N] [--rate-mbps N] [--api-key KEY]
                   [--noaa-satellite NAME] [--noaa-product NAME]
                   [--noaa-year YYYY] [--noaa-day DDD] [--noaa-hour HH]

### 通用参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--source` | `eumetsat` | 数据源：`eumetsat` 或 `noaa` |
| `-o, --output` | `./downloads` | 输出目录 |
| `-w, --workers` | `32` | 并发线程数 |
| `--chunk-mb` | `8` | 分块大小，单位 MB |
| `--rate-mbps` | `200` | 全局速率上限，单位 MB/s，`0` 为不限 |
| `--api-key` | — | EUMETSAT API key（也可用环境变量） |

### NOAA 专用参数

| 参数 | 说明 |
|---|---|
| `--noaa-satellite` | 卫星代号 |
| `--noaa-product` | 产品路径 |
| `--noaa-year` | 年份 |
| `--noaa-day` | 年积日（1-366） |
| `--noaa-hour` | 小时（0-23） |

### 示例

拉取 EUMETSAT MSG HRSEVIRI 指定时段：

    skygrab --source eumetsat -o ./msg_data \
      --workers 32 --chunk-mb 8 --rate-mbps 200

拉取 NOAA GOES-16 ABI L1b 全盘辐射数据：

    skygrab --source noaa -o ./goes16_data \
      --noaa-satellite goes16 \
      --noaa-product ABI-L1b-RadF-Reproc \
      --noaa-year 2017 --noaa-day 351 --noaa-hour 0 \
      --workers 32 --chunk-mb 8

拉取 NOAA NOAA-20 VIIRS 数据：

    skygrab --source noaa -o ./n20_data \
      --noaa-satellite n20 \
      --noaa-product VIIRS-JRR-EDR \
      --noaa-year 2024 --noaa-day 100 --noaa-hour 12

---

## 🎛️ 推荐配置

| 场景 | 线程 | 块大小 | 限速 |
|---|---|---|---|
| 家用宽带 | 16 | 8 MB | 50 MB/s |
| 数据中心 | 32 | 8 MB | 200 MB/s |
| 激进（自担风险） | 64 | 4 MB | 0（不限） |
| 保守（共享网络） | 8 | 16 MB | 20 MB/s |
| 小文件为主 | 16 | 2 MB | 100 MB/s |

> **提示**：激进模式会显著增加服务端压力，可能触发临时封禁。建议先用
> 保守配置测一次，确认无误后再逐步提高。

---

## ⌨️ TUI 快捷键

| 键 | 动作 |
|---|---|
| `s` | 搜索 |
| `d` | 下载选中产品 |
| `c` | 取消当前下载 |
| `q` | 退出 |
| `Tab` / `Shift+Tab` | 切换焦点 |
| `↑` / `↓` | 列表导航 |
| `Space` | 勾选 / 取消勾选 |
| `Enter` | 触发当前焦点控件 |

---

## 🏗️ 架构

    ┌──────────────────────────────────────────────────────┐
    │                skygrab.app (TUI)                     │
    │  ┌────────────┐  ┌────────────┐  ┌────────────────┐  │
    │  │ TopBar     │  │ ProductList│  │ DownloadItems  │  │
    │  └────────────┘  └────────────┘  └────────────────┘  │
    └───────────────────────┬──────────────────────────────┘
                            │ call_from_thread
                            ▼
    ┌──────────────────────────────────────────────────────┐
    │           skygrab.engine.DownloadEngine              │
    │  ┌────────────┐  ┌────────────┐  ┌────────────────┐  │
    │  │ RateLimiter│  │ ChunkPlan  │  │ ProgressReport │  │
    │  └────────────┘  └────────────┘  └────────────────┘  │
    │                        │                             │
    │            ThreadPoolExecutor (N workers)            │
    │                        │                             │
    │         os.pwrite → .part 文件（并行偏移写入）         │
    └───────────────────────┬──────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
    ┌──────────────────┐          ┌──────────────────┐
    │ sources.eumetsat │          │   sources.noaa   │
    │ Data Store API   │          │   S3 REST API    │
    └──────────────────┘          └──────────────────┘

### 目录结构

    skygrab/
    ├── pyproject.toml
    ├── README.md
    ├── LICENSE
    ├── requirements.txt
    ├── requirements-dev.txt
    ├── docs/
    │   └── architecture.md
    ├── src/skygrab/
    │   ├── __init__.py
    │   ├── __main__.py
    │   ├── cli.py            # argparse 入口
    │   ├── app.py            # Textual TUI
    │   ├── engine.py         # 下载引擎
    │   ├── ratelimit.py      # 令牌桶
    │   ├── progress.py       # 线程安全进度聚合
    │   ├── util.py           # 工具函数
    │   ├── sources/
    │   │   ├── base.py
    │   │   ├── eumetsat.py
    │   │   └── noaa.py
    │   └── widgets/
    │       ├── download_item.py
    │       └── topbar.py
    └── tests/

### 核心设计

**分块并发**：每个文件按 `--chunk-mb` 切块，每块由一个线程通过 HTTP
`Range` 请求拉取，使用 `os.pwrite` 按偏移量写入同一个 `.part` 文件。

**全局限速**：令牌桶在全部线程间共享。即使 64 个线程同时请求，消费速率
也被控制在 `--rate-mbps` 以内。

**断点续传**：每个产品的已完成块索引保存在 `.state.json`。中断后重新
运行，已完成块会被跳过。

**S3 与 EUMETSAT 分离**：S3 公开桶不接受 `Authorization: Bearer` 头，
SkyGrab 为 S3 请求维护一个独立的、无认证的 `requests.Session`。

---

## ❓ 常见问题

### NOAA 下载报 400 Bad Request

S3 公开桶不接受 EUMETSAT 的 `Authorization: Bearer` 头。SkyGrab 已自动
为 S3 请求切换到无认证 Session。若你修改了代码，请确认所有 S3 请求都走
`s3_session` 而不是 `session`。

### 搜不到数据

NOAA 的 S3 是"存在即列出"，没有数据就是没有。用下面的命令先确认：

    curl -s "https://noaa-goes16.s3.amazonaws.com/?list-type=2&prefix=ABI-L1b-RadF-Reproc/2017/351/00/&max-keys=5"

如果 `<Contents>` 为空，说明该日期下确实无数据，换一个时段。

### 下载中断了怎么办

直接重跑。SkyGrab 会读取 `.state.json` 跳过已完成块。要彻底重来：

    rm downloads/<产品名>.part
    rm downloads/<产品名>.state.json

### 可以下载 SatDump 的 baseband 数据吗

只有通过 AWS Ground Station 已购 contact 的 pcap 才包含原始 IQ。SkyGrab
支持从用户自己的 S3 bucket 拉取这些 pcap，但下载后需要额外后处理器提取
IQ 并生成 SatDump 可识别的 `.satdump` 元数据文件。

### 会不会被服务端封禁

默认限速 200 MB/s，对大多数服务端是安全的。如果你改成 `--rate-mbps 0`
（不限速），并开到 64 线程，有可能触发临时封禁。建议从默认值开始。

### 输出的文件在哪

默认在 `./downloads/`。NOAA 模式下会按 bucket 名分子目录：

    downloads/
    ├── noaa-goes16/
    │   └── RP_ABI-L1b-RadF-M3C01_G16_s20173510000418_...nc
    └── noaa-nesdis-n20-pds/
        └── ...

---

## 🧪 开发

    # 安装开发依赖
    pip install -e '.[dev]'

    # 运行测试
    pytest

    # 代码风格
    ruff check src/
    black src/ tests/

    # 类型检查
    mypy src/skygrab

### 添加新数据源

1. 在 `src/skygrab/sources/` 下创建新模块
2. 继承 `sources.base.DataSource`
3. 实现 `list(...)` 返回产品列表
4. 在 `cli.py` 与 `app.py` 中注册

---

## 🗺️ Roadmap

- [ ] AWS Ground Station pcap 后处理器
- [ ] 下载完成后自动触发 SatDump pipeline
- [ ] 块级 hash 校验
- [ ] Prometheus 指标导出
- [ ] 更多数据源：Copernicus、NASA Earthdata
- [ ] 并发产品级下载（目前产品串行、块并行）
- [ ] 配置文件支持（`.skygrab.toml`）

---

## 📄 License

MIT © 2026 kase

---

## 🙏 致谢

- [SatDump](https://github.com/satdump/satdump) — 下游解码器
- [Textual](https://textual.textualize.io/) — TUI 框架
- [NOAA NODD](https://www.noaa.gov/information-technology/open-data-dissemination) — 公开数据
- [EUMETSAT](https://data.eumetsat.int/) — 数据服务
