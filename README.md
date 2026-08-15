# telegram-ai-bot（可切换模型）

一个基于 Python 构建的轻量级、高度可扩展的 Telegram AI 机器人框架。支持 Webhook 部署，具备多轮对话、联网搜索、图片分析、群聊上下文、群聊总结及 AI 模型切换等能力。

---

## 📂 项目结构

* **`main.py`**：Flask Web 服务、Telegram Webhook 入口、安全验证、应用初始化及机器人命令菜单。
* **`config.py`**：API 配置、默认模型及可用模型配置。
* **`bot_logic.py`**：Telegram 消息处理、@机器人、回复机器人、群聊历史、群聊总结及主要对话逻辑。
* **`ai_logic.py`**：AI API 调用、模型切换及图片分析。
* **`utils.py`**：引用消息处理、联网搜索及 Telegram 消息排版等通用功能。
* **`requirements.txt`**：项目运行所需的 Python 依赖。
* **`README.md`**：项目说明文档。

---

## 🤖 AI 服务

本项目采用 OpenAI 兼容格式的调用方式，**AI 厂商无关**。你可以轻松接入不同的 AI 服务（如 OpenAI、DeepSeek、兼容 API 或自建模型）。

当前默认使用：

* `agnes-2.0-flash`

同时支持通过机器人 `/choose` 菜单切换其他可用模型。

* `agnes-2.0-flash`
* `agnes-2.5-flash`
* `agnes-2.5-pro`
* `agnes-2.5-pro-alpha`

用户可以通过 Telegram 的交互式按钮选择模型。

---

## 🖼️ 图片分析

机器人支持接收 Telegram 图片，并使用 AI 对图片进行理解和分析。

例如可以直接发送图片并提问，或者回复一张图片进行提问。

本项目目前**不提供图片生成和视频生成功能**，仅保留图片分析能力。

---

## 🔒 隐私与安全

**重要安全提示：**
1. **切勿将 API Key 写入代码**：请使用环境变量（Environment Variables）读取。
2. **切勿泄露 `.env`**：如果本地调试使用 `.env` 文件，请确保将其加入 `.gitignore`。
3. **切勿公开 Telegram Bot Token**：严禁提交到 GitHub、README 或公开群聊。
4. **Webhook Secret**：建议启用 `WEBHOOK_SECRET`，通过 `X-Telegram-Bot-Api-Secret-Token` 确保只有来自 Telegram 官方的合法请求才会被处理。

### 消息隐私说明
Telegram 消息在接入机器人后会转发给第三方 AI 服务。如果你的机器人开启了**联网搜索、图片分析、群聊历史、引用消息**等功能，部分内容可能会发送给 AI 服务。建议在正式部署前向用户明确告知，避免发送敏感信息。

---

## 🚀 部署指南

支持部署在 Render、Railway、VPS 等支持 Python + Webhook 服务的平台。

**推荐环境变量配置：**
* `TELEGRAM_BOT_TOKEN`
* `WEBHOOK_SECRET`
* `AGNES_API_KEY`

---

## 📝 日志与排错

支持在控制台输出详细日志，方便监控：
* 接收 Telegram 消息请求
* 检查 Webhook 签名是否正常
* 检查 Telegram 是否成功推送 Update
* 检查 AI API 是否响应顺畅
* 检查模型切换及图片分析是否正常

*注意：日志中严禁输出 API Key、Bot Token 或敏感明文消息。*

---

## 🚀 后续扩展

* 更多 AI 模型
* 多 AI 服务商
* 长期记忆
* 联网搜索优化 / 网页内容解析
* PDF 解析
* 语音识别 (STT) 与语音合成 (TTS)
* 用户权限系统

---

## 📄 License

本项目仅供学习、研究和个人使用。

---

## 🎁 特别鸣谢

在这里非常感谢各位大佬的观看，也特别感谢[@hwxlikemi](https://github.com/hwxlikemi) 对本项目提供的帮助与支持！
