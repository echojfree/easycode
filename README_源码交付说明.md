# EasyCode 源码交付说明

## 项目定位

`EasyCode` 是一个基于 Python 实现的本地 AI Agent CLI 学习版项目。这个项目的出发点，不是做一个商业成品，而是为了学习和拆解 `Claude Code` 这类终端 Agent 产品是怎么被设计出来的、为什么会这样设计、核心原理落在什么地方。

适合以下用途：

- 学习 Claude Code 类产品的基础架构
- 研究 Agent Loop、Tool Use、上下文管理、文件编辑策略
- 研究文件读写、命令执行、MCP 接入的实现思路
- 作为理解 AI 编程助手原理的学习样例
- 在理解原理之后继续做自己的二次开发

本项目更偏原理学习版、研究版、拆解版，不属于商业成品 SaaS 系统。

## 当前源码包含内容

- 核心入口：`main.py`
- Agent 主流程：`scc/agent.py`
- CLI 交互：`scc/cli.py`
- API 通信：`scc/api.py`
- 内置工具集：`scc/tools/`
- MCP 相关实现：`scc/mcp/`
- 依赖配置：`requirements.txt`
- 环境示例：`.env.example`
- 学习文档：`docs/study_guide.md`
- 设计与计划文档：`docs/superpowers/`
- 测试代码：`test/`、`test_full.py`、`test_mcp.py`
- 原理解读材料：`wechat_article.md`
- 示例辅助文件：`fake_mcp_server.py`

## 运行环境

- Python 3.12 或接近版本
- 本地已安装 Ollama
- 模型建议：`qwen2.5-coder:7b`

## 快速运行

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 复制环境变量示例并按需修改

```bash
copy .env.example .env
```

3. 启动项目

```bash
python main.py
```

## 交付范围

本压缩包默认交付：

- 完整源码
- 基础目录结构
- 依赖文件
- 测试文件
- 学习说明文档
- 原理拆解资料

本压缩包默认不包含：

- 已配置好的私有密钥
- 已安装的虚拟环境
- 服务器部署服务
- 远程代安装
- 长期售后维护
- 商业授权承诺

## 已做基础验证

本地已执行测试：

- `python -m pytest -q`
- 结果：`48 passed`

说明：测试通过代表当前代码在本地检查通过，但买家电脑环境、模型配置、Python 版本不同，仍可能需要自行调整。

## 适合买家类型

- 有 Python 基础的开发者
- 想研究 AI Agent / Claude Code 类产品原理的人
- 想搞清楚 Claude Code 为什么要这样设计工具链和循环的人
- 想基于本项目继续改造成自己的本地工具的人

## 不适合买家类型

- 零基础小白，买来即要求一键赚钱
- 需要成品商业后台和运营系统
- 需要完整商用部署、收款、用户系统、管理后台的人

## 使用提示

- 建议先读 `docs/study_guide.md`
- 如需理解整体设计和原理拆解，继续看 `docs/superpowers/specs/` 和 `docs/superpowers/plans/`
- 如需测试功能，可先运行测试文件再进入交互模式

## 风险提示

- 本项目依赖本地模型或模型接口能力，模型不同，表现差异会比较明显
- Agent 类项目本身具有试验性质，更适合拿来理解原理、学习架构和做实验，不建议直接承诺商业生产可用
- 买卖源码时建议如实说明交付边界，避免因“预期不一致”引发售后纠纷
