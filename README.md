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
