# ASR 方向代码结构与现有流程

这是统一交接包中的 `README-ASR.md`。先看 `智控台操作指南.md`，再按本页定位识别链路；需要服务器操作时看 `服务器操作指南.md`。

包内三个项目是本地完整源码快照。本方向先看 `xiaozhi-esp32-server/main/xiaozhi-server/` 的语音识别链路，再根据使用的是 ESP32 设备还是 Flutter 应用端，追溯音频上传路径。上游项目中的其他功能也保留在包里，方便查看调用关系。

## 三个工程各有什么

| 目录 | 内容 | ASR 方向的重点 |
| --- | --- | --- |
| `xiaozhi-esp32-server/main/xiaozhi-server/` | Python 核心服务、配置模板、WebSocket、音频、VAD、ASR、LLM、TTS | WebSocket 接入、音频接收、断句和识别 |
| `xiaozhi-esp32-server/main/manager-api/` | Java 管理 API | 智能体与模型配置怎样进入核心服务 |
| `xiaozhi-esp32-server/main/manager-web/` | 智控台 Vue 前端 | 语音识别模型配置界面 |
| `xiaozhi-esp32-server/main/manager-mobile/` | 移动管理端源码 | 本方向通常先不用读 |
| `xiaozhi-esp32-main/` | ESP32 固件完整源码 | 麦克风采集、音频前处理、Opus 编码和上传 |
| `FlutterClient/active/source-code/` | Flutter 应用端完整源码及 Android/Windows 工程 | 麦克风采集、WebSocket 连接和音频上传 |

## 从说话到识别文字

ESP32 路径：学生说话 → 板载麦克风采集 → 固件按板型和编译配置做前处理、编码 → WebSocket 上传 → 服务端接收音频、判断语音结束 → ASR 模型输出文字。

Flutter 路径：应用端采集麦克风 → WebSocket 上传 → 进入同一个服务端音频接收与识别链路。识别文字之后才进入知识库检索、LLM 回答和 TTS 播报。

历史记录中的服务端 ASR 是带物理实验热词的 SeACo-Paraformer；线上当前模型与参数尚待核对。课堂嘈杂可能影响拾音与识别，但成因尚未确认。固件中的 AFE、降噪和 AEC 代码是否在当前设备有效启用，也要根据实机版本确认。

10-11服务器源码还发现了纠错词管理相关的Java和前端代码，管理API客户端包含 `get_correct_words`；本包仍按本地源码提供，尚未包含这组服务器独有文件。它们是否被当前ASR推理流程使用还未核实。音频接收与ASR主链路的上述阅读路径可直接用来了解现有实现。

## 关键文件和阅读顺序

| 顺序 | 相对包根的路径 | 看什么 |
| --- | --- | --- |
| 1 | `xiaozhi-esp32-main/main/boards/xingzhi-cube-1.54tft-wifi/config.h`、`xingzhi-cube-1.54tft-wifi.cc` | 当前记录板型、I2S 麦克风、音频器件 |
| 2 | `xiaozhi-esp32-main/main/audio/`、`main/protocols/`、`sdkconfig` | 音频处理、编码、发送、编译开关 |
| 3 | `FlutterClient/active/source-code/lib/services/xiaozhi_service.dart`、`xiaozhi_websocket_manager.dart` | 应用端采集、设备标识、WebSocket 连接 |
| 4 | `xiaozhi-esp32-server/main/xiaozhi-server/core/websocket_server.py` | 服务端连接入口 |
| 5 | `xiaozhi-esp32-server/main/xiaozhi-server/core/handle/receiveAudioHandle.py` | 音频帧接收、断句与 ASR 调用 |
| 6 | `xiaozhi-esp32-server/main/xiaozhi-server/core/providers/vad/`、`core/providers/asr/` | VAD 和 ASR 接口及实现；重点看 `asr/fun_local.py` |
| 7 | `xiaozhi-esp32-server/main/xiaozhi-server/core/connection.py` | 识别文字怎样进入后续对话 |
| 8 | `xiaozhi-esp32-server/main/manager-web/src/`、`manager-api/src/` | 智控台 ASR 模型配置及其后端 |

管理端、固件和 Flutter 工程各自有上游 README、构建元数据及更多源码目录。本包包含这些本地源文件；总入口 `README.md` 说明源码范围和上游项目。服务器登录方法见 `服务器操作指南.md`，账号已确定为 `devuser`，密码只在服务器指南开头填写；实际权限由负责人确认。
