# agnes-bot

一个基于 Python 构建的轻量级、高度可扩展的 Telegram AI 机器人框架。支持 Webhook 部署，具备多轮对话、联网搜索、图片分析及群聊上下文处理能力。

---

## 📂 项目结构

* **`main.py`**：Flask Web 服务、Telegram Webhook 入口、安全验证、应用初始化。
* **`bot_logic.py`**：AI 对话逻辑、消息路由、图片分析、联网搜索、群聊处理及 Telegram 处理器。
* **`requirements.txt`**：项目运行所需的 Python 依赖。
* **`README.md`**：项目说明文档。

---

## 🤖 AI 服务

本项目采用 OpenAI 兼容格式的调用方式，**AI 厂商无关**。你可以轻松接入不同的 AI 服务（如 OpenAI、DeepSeek、兼容 API 或自建模型）：

* 确保第三方服务支持兼容 OpenAI API 的请求格式。
* 在环境变量中配置对应的 API Key 与 Base URL 即可无缝切换。

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
* `OPENAI_API_KEY`
* `OPENAI_API_BASE` (可选)
* `MODEL_NAME` (可选)

---

## 📝 日志与排错

支持在控制台输出详细日志，方便监控：
* 接收 Telegram 消息请求
* 检查 Webhook 签名是否正常
* 检查 Telegram 是否成功推送 Update
* 检查 AI API 是否响应顺畅

*注意：日志中严禁输出 API Key、Bot Token 或敏感明文消息。*

---

## 🚀 后续扩展

* 多 AI 模型切换 / 多 AI 服务商
* 长期记忆
* 联网搜索优化 / 网页内容解析
* PDF 解析
* 语音识别 (STT) 与语音合成 (TTS)
* 用户权限系统

---

## 📄 License

本项目仅供学习、研究和个人使用。
