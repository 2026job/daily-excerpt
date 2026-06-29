# 每日精美文摘小程序

这是一个微信小程序 MVP 项目，用于验证“每天自动更新一篇精美短文摘，用户打开即可阅读，并可回看历史”的核心体验。

## 当前目标

- 固定公开来源采集素材。
- 规则清洗正文并修正文段。
- 使用云 OCR API 辅助识别图片文字。
- 抓取失败时从素材池补发。
- 将每日文摘发布到微信云数据库。
- 微信小程序展示今日文摘、历史列表和详情页。

## 本地测试

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

## 本地 dry run

```bash
python3 scripts/build_daily_excerpt.py --dry-run --date 2026-06-28
```

Dry run 会把输出写入 `data/output/`，不会调用微信云数据库。

## 环境变量

生产发布时使用：

- `WECHAT_CLOUD_ENV_ID`
- `WECHAT_APP_ID`
- `WECHAT_APP_SECRET`
- `XHS_NOTE_URL`
- `TENCENT_SECRET_ID`
- `TENCENT_SECRET_KEY`
- `TENCENT_OCR_REGION`

不要把真实密钥提交到仓库。

## 微信小程序开发

用微信开发者工具打开 `miniprogram/` 目录。首次接入真实云开发环境时，需要：

1. 将 `miniprogram/project.config.json` 中的 `appid` 替换成真实小程序 AppID。
2. 在微信开发者工具中开通云开发。
3. 创建 `excerpts`、`sources`、`material_pool`、`job_logs` 集合。
4. 配置数据库权限，让普通用户只能读取 `status = "published"` 的文摘。
5. 在 GitHub Actions Secrets 中配置微信云开发和 OCR 凭据。

第一版可以先用 `python3 scripts/build_daily_excerpt.py --dry-run` 验证文摘生成，再接入真实微信云数据库发布。

## GitHub Actions 自动更新 MVP

当前 workflow 会每天运行一次，也支持手动触发。前期不写入微信云数据库，只生成 `data/output/excerpts.json` 和 `data/output/job_logs.json` artifact。

在 GitHub 仓库的 Actions Secrets 中配置：

- `XHS_NOTE_URL`：公开小红书笔记 URL。未配置时会使用仓库内 fixture 做 dry-run。
- `TENCENT_SECRET_ID`、`TENCENT_SECRET_KEY`、`TENCENT_OCR_REGION`：可选 OCR 凭据。未配置时只使用 HTML 正文清洗。

workflow 会显式使用北京时间日期：

```bash
TZ=Asia/Shanghai date +%F
```

## 候补素材池自动补充

GitHub Actions 现在也会在每小时第 7 分钟和第 37 分钟运行一次素材补充流程。每次运行会抓取“欣欣的阅读疗愈记”的公开主页首屏帖子列表，并最多处理 1 篇尚未进入候补池的新帖子。

如果公开主页能提供详情 URL，脚本会抓取详情正文并追加到 `data/material_pool/seed.json`，由 Action 自动提交回仓库。如果公开主页只暴露标题和封面，脚本会先把元信息保存到 `data/material_pool/xiaohongshu_candidates.json`，等待后续有可用 URL 或浏览器授权方案时再升级为正文素材。补充日志写入 `data/output/material_replenishment_logs.json`，随 Actions artifact 一起保存，方便查看抓取失败、解析失败或没有新素材的原因。

这一步仍然遵循保守边界：只读取公开页面，不绕过登录、验证码、风控或私密内容限制。
