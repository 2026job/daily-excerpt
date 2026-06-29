# 半小时候补素材补充设计

## 目标

前期将“欣欣的阅读疗愈记”的其他公开帖子作为候补素材来源：独立 GitHub Actions workflow 每半小时运行一次，每次最多处理 1 篇新候选。每日文摘发布逻辑暂时保持现状，候补池逐步积累，后续可升级为“每天自动抓最新帖并推送”。

## 范围

本阶段只做素材补充，不改变当前 Pages 展示和每日文摘的优先发布策略。抓取遵循现有保守边界：只读取公开 HTML/SSR 数据，不绕过登录、验证码、风控或私密内容限制。

## 数据流

1. `Material Replenishment` workflow 定时触发 `scripts/replenish_material_pool.py`。
2. 脚本抓取或读取缓存中的博主主页首屏帖子列表。
3. 脚本读取现有 `data/material_pool/seed.json` 和已发布 `data/output/excerpts.json`。
4. 脚本跳过已发布、已在候补池、URL/note_id/content_hash 重复的帖子。
5. 脚本按列表顺序尝试最新候选，每次最多处理 1 篇。
6. 详情抓取成功后清洗正文、生成 summary/content_hash，并追加到 `seed.json`，状态为 `candidate`。
7. 公开主页未提供详情 URL 时，将标题、封面、profile URL 等元信息追加到 `xiaohongshu_candidates.json`，状态为 `candidate_metadata`。
8. 详情抓取失败时写入补充日志，不把不可用正文放入 `seed.json`。
9. 如果 `seed.json` 或 `xiaohongshu_candidates.json` 有变化，Action 自动 commit 并 push 回 main。

## 文件职责

- `scripts/replenish_material_pool.py`：候补池补充入口，负责编排主页列表、详情抓取、去重、追加和日志。
- `scripts/excerpt_pipeline/material_pool.py`：保留现有读取和 fallback 选择逻辑，新增必要的保存/去重辅助函数。
- `.github/workflows/material-replenishment.yml`：独立半小时 schedule，授予 contents 写权限，提交候补池变化。
- `.github/workflows/daily-excerpt.yml`：保持每日发布和 Pages 部署，不承担半小时补池。
- `tests/test_replenish_material_pool.py`：覆盖去重、成功补 1 篇、抓取失败不污染候补池。
- `README.md`：补充半小时候补池说明和自动 commit 行为。

## 错误处理

- 主页抓取失败：脚本退出非零，并写出本地日志文件，Action 显示失败，方便检查。
- 没有新候选：脚本成功退出，不提交空变更。
- 详情解析失败：记录失败项，本次运行结束，避免半小时任务一次请求多篇详情。
- 候补池 JSON 损坏：脚本退出非零，避免覆盖人工内容。

## 验收标准

- 本地测试通过。
- 用 fixture 跑补充脚本时，当前公开主页无详情 URL 的情况下能向临时候选池追加 1 条 `candidate_metadata`。
- 重复运行不会重复追加同一篇。
- workflow 每半小时触发一次，且只有 `seed.json` 或 `xiaohongshu_candidates.json` 变化时自动 commit。
