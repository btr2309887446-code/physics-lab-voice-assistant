# 大学物理实验语音智能助教（小智助手）

面向大学物理实验课程的**语音问答助教**。学生对着一个 1.54 寸屏的语音盒子提问，系统检索课程知识库、用大模型作答，并把答案**念出来 + 打字幕**。

本项目基于三个开源项目做二次开发，服务于复旦大学物理实验教学场景。

---

## 这套系统怎么工作

```
学生说话
  → ESP32 设备采集（单麦 + 乐鑫 AFE 前处理）
  → Opus / WebSocket 上传
  → xiaozhi-server（Python）
      ├─ Silero VAD 断句
      ├─ ASR：FunASR SeACo-Paraformer（带物理实验术语热词）
      ├─ 知识库预查：RAGFlow 检索（本项目自研，跳过第一次 LLM 推理）
      ├─ LLM：本地 Ollama GLM-4.7-Flash
      └─ TTS：Edge-TTS
  → 设备播放语音 + 显示字幕
```

配置从**智控台**（Web 管理后台）下发，知识库文档也从智控台上传，经 manager-api 交给 RAGFlow 解析切块。

## 目录结构

| 目录 | 内容 | 跑在哪 |
| --- | --- | --- |
| [`xiaozhi-esp32-server/`](xiaozhi-esp32-server/) | 服务端：Python 核心 + Java 管理 API + Vue 智控台 + 移动管理端 | 服务器 |
| [`xiaozhi-esp32-main/`](xiaozhi-esp32-main/) | ESP32-S3 固件（当前板型 `xingzhi-cube-1.54tft-wifi`） | 设备 |
| [`FlutterClient/`](FlutterClient/) | Flutter 客户端（Android / Windows） | 手机 / PC |
| [`knowledge-base/`](knowledge-base/) | 6 篇实验知识库（Markdown，供 RAGFlow 检索） | — |
| [`docs/`](docs/) | 交接文档：ASR / RAG / 硬件三条线的代码导读、服务器与智控台操作指南 | — |
| [`patches/`](patches/) | 修复补丁（见下文） | — |
| [`notes/`](notes/) | 问题诊断与改进方案 | — |

> `docs/` 里的文档原本是交接包根目录下的文件，里面写「相对包根的路径」时指的是本仓库根目录，因此 `xiaozhi-esp32-server/...` 这类路径仍然直接可用。

## 上游来源

| 组件 | 上游仓库 | 许可 |
| --- | --- | --- |
| 服务端 + 智控台 | [xinnan-tech/xiaozhi-esp32-server](https://github.com/xinnan-tech/xiaozhi-esp32-server) | MIT |
| ESP32 固件 | [78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) | MIT |
| Flutter 客户端 | [TOM88812/xiaozhi-android-client](https://github.com/TOM88812/xiaozhi-android-client) | Apache-2.0 |

**上游代码只提供基础架构，本项目在其之上做了修改。** 自研部分主要有：

- 知识库预查（在 LLM 推理前直接调 RAGFlow，省掉一轮推理）
- 检索失败的三档兜底策略（`kb_failure_mode`）
- `[LATENCY]` 端到端延迟埋点
- 对话历史污染修复、工具调用提醒机制
- 语音识别偏差词记录（知识库 EXP05/EXP06 的 I 类）
- 本次的「后台信息泄漏」修复（见 `patches/`）

自研改动高度集中在 [`xiaozhi-esp32-server/main/xiaozhi-server/core/connection.py`](xiaozhi-esp32-server/main/xiaozhi-server/core/connection.py) 一个文件里。**想读懂这套系统，精读这个文件即可。**

## 已知问题与当前状态

⚠️ **本仓库是代码备份，不等于线上运行版本。** 服务器上的实际部署与本地快照存在差异（交接文档记载：125 处哈希不同、110 个服务器独有文件）。因此本仓库适合用来阅读、追溯和开发，但不能据此判断线上行为。

已知待办（详见 [`notes/`](notes/)）：

1. 学生反馈「字幕里出现 `search_from_ragflow`」——已修复，见 `patches/`
2. 字幕单行滚动、切换过快，来不及阅读
3. 操作提示应「一次只讲一步、等确认再继续」
4. 回答有时过长
5. 嘈杂环境下识别率差（固件降噪实际未启用、单麦无 AEC）
6. 缺少暂停 / 重播 / 查看上一条

## 修复补丁

[`patches/修正_后台信息泄漏.patch`](patches/修正_后台信息泄漏.patch) 修复「后台信息串进字幕」问题，涉及 9 个文件：

- 服务端 6 个：工具状态改走独立 `tool` 消息类型；流式工具调用文本不再漏进 TTS；报错不再把运维话术念给学生；工具名换成人话（"让我查一下资料…"）；回答前亮 🤔 思考表情
- 固件 1 个：过滤 `% ` 前缀；`tool` 消息显示到状态栏
- 客户端 2 个：显示服务端下发的人话提示

应用方式（在仓库根目录）：

```bash
git apply --check patches/修正_后台信息泄漏.patch   # 先干跑
git apply patches/修正_后台信息泄漏.patch
```

回滚：`git apply -R patches/修正_后台信息泄漏.patch`

## 安全与合规

- **本仓库已脱敏**：智控台管理员密码已替换为占位符。若你持有更早的副本，请视为密码已泄露并立即改密。
- 服务器内网地址仍保留在文档中（RFC1918 私有地址，公网不可达），便于团队操作。
- `knowledge-base/` 下的内容整理自课程讲义与学生问答记录，**仅用于课程内部教学**。对外使用前请确认课程材料的使用范围。
- 仓库**不包含**：服务器私有配置（`data/.config.yaml`）、RAGFlow 密钥、模型权重、APK 与源码压缩包、课程原始讲义。

## 硬件

星智 Cube 1.54TFT WiFi 版（ESP32-S3，16MB Flash / 8MB PSRAM，单麦，三个按键：BOOT / 音量+ / 音量−）。
