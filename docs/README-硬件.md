# 硬件方向代码结构与现有流程

这是统一交接包中的 `README-硬件.md`。先看 `智控台操作指南.md`，再按本页定位板型与音频代码；需要服务器操作时看 `服务器操作指南.md`。

包内三个项目是本地完整源码快照。本方向先看 `xiaozhi-esp32-main/`。当前板型记录为星智 Cube 1.54TFT WiFi / ESP32-S3；实际上使用的硬件批次、已刷固件和音频开关还需结合实机确认。

## 三个工程各有什么

| 目录 | 内容 | 硬件方向的重点 |
| --- | --- | --- |
| `xiaozhi-esp32-main/main/` | 固件主程序、板级实现、音频、协议、显示与资源 | 当前板型、音频采集和上传 |
| `xiaozhi-esp32-main/partitions/`、`sdkconfig`、`dependencies.lock` | 分区、编译配置和组件依赖 | 固件配置如何影响音频能力 |
| `xiaozhi-esp32-server/main/xiaozhi-server/` | Python 核心服务 | 设备音频上传后的接收入口 |
| `xiaozhi-esp32-server/main/manager-api/`、`manager-web/`、`manager-mobile/` | 智控台后端、Web 与移动管理端 | 设备绑定和智能体配置 |
| `FlutterClient/active/source-code/` | Flutter 应用端源码 | 另一种语音入口，可与 ESP32 路径对照 |

## 设备音频流程

麦克风采集 PCM → 固件按板型与编译配置做音频前处理 → Opus 编码 → WebSocket 上传 → 服务端接收、断句与 ASR 识别 → 回答音频下发并在扬声器播放。

该板型记录为单麦。上游音频模块含 AFE、降噪、AEC 等代码，不代表当前设备已启用或实际有效。具体状态要结合板型代码、`sdkconfig`、已刷固件与实机表现。课堂嘈杂可能影响识别，但还没有结论证明单由硬件引起。

## 关键文件和阅读顺序

| 顺序 | 相对包根的路径 | 看什么 |
| --- | --- | --- |
| 1 | `xiaozhi-esp32-main/README_zh.md`、`CMakeLists.txt`、`main/CMakeLists.txt` | 上游工程和主组件 |
| 2 | `xiaozhi-esp32-main/main/boards/xingzhi-cube-1.54tft-wifi/config.h`、`xingzhi-cube-1.54tft-wifi.cc` | 当前记录板型的引脚、编解码器和设备类 |
| 3 | `xiaozhi-esp32-main/main/application.cc`、`main/main.cc` | 设备启动与应用生命周期 |
| 4 | `xiaozhi-esp32-main/main/audio/audio_service.cc`、`main/audio/processors/` | 麦克风输入、输出播放、前处理和编解码 |
| 5 | `xiaozhi-esp32-main/main/protocols/` | 服务端连接与音频消息传输 |
| 6 | `xiaozhi-esp32-main/sdkconfig`、`sdkconfig.defaults*`、`partitions/` | 编译选项和分区 |
| 7 | `xiaozhi-esp32-server/main/xiaozhi-server/core/websocket_server.py`、`core/handle/receiveAudioHandle.py` | 服务器怎样接收设备音频 |
| 8 | `xiaozhi-esp32-server/main/manager-api/src/main/java/xiaozhi/modules/device/` | 管理端设备记录与绑定 |

工程自带的 `docs/` 和 `main/audio/README.md` 是上游通用资料。包内有完整本地源文件，未带构建缓存、下载组件和历史固件二进制；已刷版本不能仅由源码推断。智控台登录与设备管理入口见包根 `智控台操作指南.md`。服务器登录方法见 `服务器操作指南.md`，账号已确定为 `devuser`，密码只在服务器指南开头填写；实际权限由负责人确认。
