# GitHub Actions 固定笔记 URL 自动更新设计

## 目标

将当前 GitHub Actions 从“读取仓库内 raw HTML fixture 的 dry-run”升级为“可定时抓取一个公开小红书笔记 URL，生成每日文摘 JSON artifact”。

第一版只验证 GitHub Actions 自动更新链路，不接微信云数据库，不要求小程序读取线上数据。

## 范围

包含：

- `build_daily_excerpt.py` 支持 `--note-url`。
- GitHub Actions 从 `XHS_NOTE_URL` secret 读取公开笔记 URL。
- GitHub Actions 显式传入北京时间日期。
- 未配置 `XHS_NOTE_URL` 时继续使用仓库 fixture，保证 workflow 可运行。
- 输出仍写入 `data/output/excerpts.json` 和 `data/output/job_logs.json` 并上传 artifact。
- 抓取失败、解析失败或正文为空时走现有 fallback 逻辑，并写入 job log。

不包含：

- 从账号主页自动寻找最新笔记。
- 翻页抓取。
- 绕过登录、验证码、风控。
- 写入微信云数据库。
- 小程序线上数据接入。

## 数据流

```text
GitHub Actions schedule/manual
→ 读取 XHS_NOTE_URL
→ 如果存在：build_daily_excerpt.py --note-url "$XHS_NOTE_URL"
→ 如果不存在：build_daily_excerpt.py --raw-note-html fixture
→ 抓取/解析/清洗/OCR
→ 输出 data/output/*.json
→ 上传 artifact
```

## 错误处理

- `--note-url` 抓取失败：记录失败原因，尝试 fallback 素材。
- `--note-url` 未配置：不视为失败，使用 fixture dry-run。
- OCR 未配置：继续使用 `FakeOcrClient`，只基于 HTML 正文清洗。

## 验证

- 单元/集成测试覆盖 `--note-url` 路径，使用 monkeypatch/mock 避免真实网络。
- workflow 文本检查覆盖 `XHS_NOTE_URL`、北京时间日期和 fixture fallback。
- 全量 pytest 通过。
- 本地 fixture dry-run 继续通过。
