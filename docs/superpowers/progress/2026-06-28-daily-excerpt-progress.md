# 每日精美文摘小程序进展记录

## 当前目标

按 `docs/superpowers/plans/2026-06-28-daily-excerpt-miniprogram.md` 执行，实现每日精美文摘微信小程序 MVP。

优先目标：

1. 本地 dry-run pipeline 跑通。
2. Python 测试覆盖清洗分段、fallback、OCR 抽象和 pipeline。
3. 准备 GitHub Actions、微信云发布骨架和小程序源码。

## 当前状态

- 状态：执行中。
- 执行方式：Subagent-driven development，主线程负责验证、review 和进展记录。
- 工作目录：`/Users/liangzj/projects/helloworld`。
- 分支：`main`。
- 注意：当前仓库已有大量未跟踪项目材料，执行中只 stage 本任务相关文件。

## 已完成

- 已完成产品设计文档：`docs/superpowers/specs/2026-06-28-daily-excerpt-miniprogram-design.md`。
- 已完成实现计划：`docs/superpowers/plans/2026-06-28-daily-excerpt-miniprogram.md`。
- Task 1：项目基础整理、本地测试入口、进展文档。
- Task 2：清洗分段模块。最终提交到 `6d2a668`，本地验证 `tests/test_cleaning.py` 16 passed。
- Task 3：fallback 素材池。最终提交到 `0c27159`，本地验证包含 material pool 的当前测试 27 passed，spec/code quality review 通过。
- Task 4：小红书解析 fixture 测试。提交 `56b6173`，本地验证 extractor 测试通过，review 通过。未修改现有抓取脚本。
- Task 5：OCR 抽象。提交 `0485cf0`，本地验证 OCR 测试通过，review 通过。真实腾讯云 OCR 凭据尚未配置。
- Task 6：本地 daily excerpt dry-run pipeline。最终提交 `e719896`，本地 dry-run 已生成 `data/output/excerpts.json` 和 `data/output/job_logs.json`，review 通过。
- Task 7：GitHub Actions dry-run workflow。提交 `ae7721f`，workflow 文本 sanity check 通过。
- Task 8：微信云 publisher 骨架。提交 `8102c4c`，本地验证 publisher 测试通过，review 通过。未进行真实微信云网络调用。
- Task 9：极简微信小程序源码。提交 `e36f1f2`，`app.json` 与 `project.config.json` 校验通过，review 通过。

## 进行中

- Task 10：最终 README 更新、全量测试、dry-run、JSON 校验。

## 验证记录

- `python3 -m pytest tests/test_cleaning.py -v`：失败，原因是系统 Python 环境没有安装 `pytest`。接下来创建本地 `.venv` 并安装 `requirements-dev.txt`。
- `.venv/bin/python -m pytest tests/test_cleaning.py -v`：通过，6 passed。
- Task 2 spec review：要求修改，原因是 `split_sentences` 未覆盖英文句点，测试缺少 HTML entity、CRLF、平台噪声、英文句点、新行和短段合并覆盖。
- Task 2 最终验证：`.venv/bin/python -m pytest tests/test_cleaning.py -v`：通过，16 passed。
- Task 3 验证：`.venv/bin/python -m pytest tests/test_cleaning.py tests/test_material_pool.py -v`：通过，21 passed。
- 当前集成验证：`.venv/bin/python -m pytest tests/test_cleaning.py tests/test_material_pool.py tests/test_xiaohongshu_extractors.py -v`：通过，27 passed。
- Task 6 后全量验证：`.venv/bin/python -m pytest -v`：通过，37 passed。
- Task 6 dry-run：`rm -rf data/output && .venv/bin/python scripts/build_daily_excerpt.py --dry-run --date 2026-06-28 --raw-note-html data/raw/xiaohongshu-c80cf3e1ef14.html`：成功，输出 `published excerpt local-1`。
- Task 7 workflow sanity：通过，输出 `workflow sanity ok`。
- Task 8 后全量验证：`.venv/bin/python -m pytest -v`：通过，42 passed。
- Task 9 JSON 校验：`python3 -m json.tool miniprogram/app.json` 与 `python3 -m json.tool miniprogram/project.config.json` 均通过。

## 待用户提供

后续接入真实线上环境时需要：

- 微信小程序 AppID。
- 微信云开发环境 ID。
- 微信 App Secret 或可用于云开发 OpenAPI 的凭据。
- 腾讯云 OCR `TENCENT_SECRET_ID`。
- 腾讯云 OCR `TENCENT_SECRET_KEY`。
- 腾讯云 OCR 区域，建议先用 `ap-guangzhou`。

## 后续接手提示

如果由其他 agent 接手：

1. 先读本文件。
2. 再读 implementation plan。
3. 运行 `git status --short`，确认未提交变更范围。
4. 从“当前状态”和“验证记录”继续执行。
