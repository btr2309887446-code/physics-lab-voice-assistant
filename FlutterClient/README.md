# Flutter 应用端源码说明

本目录提供项目当前使用的 Flutter 应用端主线源码，位置为 `active/source-code/`。`pubspec.yaml` 中的版本为 **`2.1.0+3`**。这份代码取自本地项目的 `FlutterClient/active/source-code/`，尚未与服务器上的应用端构建目录完成全量核对。

## 目录结构与文件作用

```text
FlutterClient/
├── README.md                 # 本说明
└── active/
    └── source-code/          # Flutter 工程根目录
        ├── lib/              # 应用界面、配置与对话逻辑
        ├── android/          # Android 原生工程与平台配置
        ├── windows/          # Windows 原生工程与平台配置
        ├── ios/、macos/、linux/、web/  # 上游保留的其他平台工程
        ├── documents/        # 上游附带的说明材料
        ├── test/             # 上游保留的测试代码
        ├── pubspec.yaml      # 应用版本、依赖与资源声明
        ├── pubspec.lock      # 依赖版本记录
        └── README.md         # 上游客户端介绍
```

项目主要使用 Android 和 Windows 应用端。其他平台工程保留在源码中，其存在不代表已经在本项目中完成适配或验证。

| 源码位置（相对于 `active/source-code/`） | 作用 |
|---|---|
| `lib/main.dart` | 应用入口与页面、状态初始化 |
| `lib/screens/`、`lib/widgets/` | 会话、语音通话、设置等页面与界面组件 |
| `lib/models/` | 消息、会话及服务配置的数据结构 |
| `lib/providers/config_provider.dart` | 应用配置的管理与保存 |
| `lib/providers/conversation_provider.dart` | 会话及消息状态的管理 |
| `lib/services/xiaozhi_service.dart` | 组织文字发送、录音、语音通话和服务器回复的处理 |
| `lib/services/xiaozhi_websocket_manager.dart` | 建立 WebSocket 连接，收发协议消息与音频数据 |
| `lib/utils/audio_util.dart` | 录音、音频播放及音频会话配置 |
| `lib/utils/device_util.dart` | 设备标识等辅助逻辑 |
| `lib/services/dify_service.dart`、`minimax_service.dart` | 上游保留的其他服务接入逻辑；本项目小智连接主要看前两项小智服务文件 |

## 为什么与项目根目录的 FlutterClient 不完全相同

项目根目录的 `FlutterClient/` 同时保存了活跃源码、历史版本目录、安装包、构建产物和维护记录。交接包选择了当前 `active/source-code/` 主线，保留该工程中的源码、平台工程、资源和依赖声明。

交接包没有收录历史版本及安装包；`.git`、`build/`、`.dart_tool/`、Gradle 缓存和本机专属的生成配置也没有收录。因此，上层目录数量不同，并不表示当前主线只交付了部分源码。源码中的实际凭证经过清理，文本文件也可能存在换行格式差异。

## 已完成的 Android 音频改动

`lib/utils/audio_util.dart` 的录音配置已使用 `AndroidAudioSource.voiceCommunication`，并启用了 `echoCancel`、`noiseSuppress` 和 `autoGain`。这些改动用于调用 Android 系统提供的回声消除、降噪和自动增益能力，针对外放声音再次进入麦克风、导致回答自打断的问题。

**目前可以确认这些配置已经写入 `2.1.0+3` 主线代码，实际平板上的效果仍待确认。** 这也不能直接证明课堂嘈杂环境中的学生语音识别问题已经解决。上述 Android 配置不能据此视为 Windows 端已完成相同处理。

## 不同方向从哪里定位应用端

- **ASR 方向**：从 `audio_util.dart` 查看录音输入，再看 `xiaozhi_service.dart` 和 `xiaozhi_websocket_manager.dart` 的音频发送过程。语音识别模型及服务端识别流程见交接包根目录 `README-ASR.md`。
- **RAG 方向**：从 `xiaozhi_service.dart` 的文字发送和回复处理、`xiaozhi_websocket_manager.dart` 的消息协议定位应用端入口。应用端负责发送问题与展示答案，知识检索的服务端流程见根目录 `README-RAG.md`。
- **硬件方向**：从 `audio_util.dart`、`android/` 和 `windows/` 查看应用端音频及平台部分；ESP32 设备固件另在包根目录 `xiaozhi-esp32-main/`，入口说明见 `README-硬件.md`。

上游应用端项目为 [TOM88812/xiaozhi-android-client](https://github.com/TOM88812/xiaozhi-android-client)。工程内部的 `source-code/README.md` 保留上游说明；本项目的目录选择和当前状态以本说明为准。
