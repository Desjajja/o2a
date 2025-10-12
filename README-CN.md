# oai2ant

基于 FastAPI 的代理服务，将 Anthropic 风格的客户端请求转换为 OpenAI 兼容的后端，同时提供 React 管理控制台。

## 功能特性
- FastAPI 代理，将 Anthropic API 调用规范化为 OpenAI 请求。
- 通过 `o2a` CLI 一键启动开发环境并支持热重载。
- React 管理界面，用于维护提供商映射并测试对话流程。
- JSON 配置文件支持分阶段发布与重启语义。

## 运行环境
- Python 3.11+（推荐使用 [`uv`](https://github.com/astral-sh/uv) 管理）。
- Node.js 18+（含 npm）用于运行管理界面。
- 推荐使用现代浏览器访问 UI。

## 安装依赖
```bash
uv sync
npm install --prefix ui
# 如果终端未自动进入虚拟环境，可手动执行
source .venv/bin/activate
# 将 CLI 安装到当前环境
uv tool install --from . oai2ant
# 或使用 pip install -e .
```

## 快速开始
仅启动代理（FastAPI + Uvicorn）：
```bash
o2a
```
默认监听 `http://0.0.0.0:8082`。健康检查位于 `/health`，Anthropic 兼容的聊天接口为 `/v1/messages`。

仅启动管理 UI（需要代理已在运行）：
```bash
o2a --ui
```
未检测到代理时命令会直接退出。请先在另一个终端执行 `o2a` 启动代理，再运行 `o2a --ui`。成功后 CLI 会在 `http://127.0.0.1:5173` 上启动 Vite（默认自动打开浏览器，可用 `--no-open-browser` 禁用），并持续运行直至按下 `Ctrl+C`。

## CLI 选项
```text
o2a [--host HOST] [--port PORT] [--reload | --no-reload]
    [--log-level LEVEL]
    [--ui] [--ui-host HOST] [--ui-port PORT]
    [--proxy-host HOST] [--proxy-port PORT]
    [--open-browser | --no-open-browser]
```
- `--host` / `--port`：设置 FastAPI 监听地址（默认 `0.0.0.0:8082`）。
- `--reload` / `--no-reload`：开启或关闭自动重载（默认开启）。
- `--log-level`：指定 Uvicorn 日志级别（默认 `info`）。
- `--ui`：仅启动 React 管理界面（若代理离线则失败）。
- `--ui-host` / `--ui-port`：重写 UI 监听地址（默认 `127.0.0.1:5173`）。
- `--open-browser`：在启用 `--ui` 时自动打开浏览器（使用 `--no-open-browser` 禁用）。
- `--proxy-host` / `--proxy-port`：`--ui` 模式下用于健康检查的代理地址（默认 `127.0.0.1:8082`）。

## 配置管理
提供商配置位于 `config/settings.json`，其结构由 `ProxyConfig` 模型校验。可通过 UI 分阶段保存并申请重启，也可以手动编辑后调用 `/admin/restart` 或 UI 按钮完成应用。

部署到生产环境时请通过环境变量提供必要的密钥，例如 `AUTH_BASIC_USER`、`AUTH_BASIC_PASS` 以及各上游 API Key。

## 开发流程
- 使用 `o2a`（或 `uv run uvicorn proxy.main:app --reload --port 8082`）运行代理。
- 使用 `o2a --ui` 或 `npm run dev --prefix ui` 迭代管理界面。
- Python 代码通过 `uv run ruff format`、`uv run ruff check` 格式化和静态检查。
- UI 代码通过 `npm run lint --prefix ui` 进行检查。

## 测试
- 后端测试：`uv run pytest`（可用 `-k streaming` 聚焦流式场景）。
- 前端单元测试：`npm test --prefix ui`。
- Cypress 端到端测试：`npm run cy:run --prefix ui`。

## 常见问题
- UI 中出现 `ECONNREFUSED` 多半是代理未运行，可重新执行 `o2a`。
- `npm run dev` 失败时请确认 Node.js ≥18，并重新安装依赖：`npm install --prefix ui`。
- 若自动重载无效，请使用 `uv sync` 重新安装依赖以确保 `watchfiles` 可用。
- `o2a --ui` 立即退出意味着健康检查失败，请确认代理可在 `http://127.0.0.1:8082/health` 访问。

## 许可
当前项目未提供显式许可协议，如需使用请联系维护者。
