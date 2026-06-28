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
