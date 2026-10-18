# 知识库 / RAG 方向代码结构与现有流程

这是统一交接包中的 `README-RAG.md`。先看 `智控台操作指南.md`，再按本页定位上传与检索链路；需要服务器操作时看 `服务器操作指南.md`。

包内三个项目是本地完整源码快照。本方向主要看 `xiaozhi-esp32-server/main/` 的智控台、管理 API 和 Python 核心服务；固件和 Flutter 是学生提问的入口，只有需要追踪请求来源时再读。

## 三个工程各有什么

| 目录 | 内容 | RAG 方向的重点 |
| --- | --- | --- |
| `xiaozhi-esp32-server/main/manager-web/` | 智控台 Vue 前端 | 知识库列表、上传、解析和智能体关联界面 |
| `xiaozhi-esp32-server/main/manager-api/` | Java 管理 API | 知识库记录、上传、RAGFlow 适配和模型配置 |
| `xiaozhi-esp32-server/main/xiaozhi-server/` | Python 核心服务 | 学生提问后检索与回答的衔接 |
| `xiaozhi-esp32-server/main/manager-mobile/` | 移动管理端源码 | 本方向通常先不用读 |
| `FlutterClient/active/source-code/` | Flutter 应用端完整源码 | 学生如何连接服务并提交语音或文字 |
| `xiaozhi-esp32-main/` | ESP32 固件完整源码 | 另一种学生提问入口 |

## 文档怎样成为回答依据

按本地代码：智控台上传文件 → manager-api 接收并调用 RAGFlow → RAGFlow 解析、切块与建立索引 → 学生提问经设备或应用端进入 xiaozhi-server → 服务端检索 RAGFlow 片段 → 主 LLM 根据问题和片段回答。新建知识库后还要在目标智能体的功能配置中关联该库；上传文件后也要确认解析完成。智控台显示的状态与线上 RAGFlow 实际内容，之后需要在线核对。

10-11服务器源码另有知识库与文档的RAGFlow状态同步方法，分别位于 `KnowledgeBaseServiceImpl.java`、`KnowledgeFilesServiceImpl.java` 和 `RAGFlowAdapter.java`；本包提供的是本地版本，不包含这几处服务器改动。这里的代码足以理解基本流程，线上知识库的实际逻辑需要结合服务器版继续核对。

## 关键目录和阅读顺序

| 顺序 | 相对包根的路径 | 看什么 |
| --- | --- | --- |
| 1 | `xiaozhi-esp32-server/main/manager-web/src/views/KnowledgeBaseManagement.vue`、`KnowledgeFileUpload.vue` | 新建知识库、上传、解析、召回测试的页面 |
| 2 | `xiaozhi-esp32-server/main/manager-web/src/views/roleConfig.vue` | 智能体如何选择知识库功能 |
| 3 | `xiaozhi-esp32-server/main/manager-api/src/main/java/xiaozhi/modules/knowledge/` | 知识库的 API、服务和数据结构 |
| 4 | `xiaozhi-esp32-server/main/manager-api/src/main/java/xiaozhi/modules/knowledge/service/impl/KnowledgeFilesServiceImpl.java` | 文件记录、上传与解析状态 |
| 5 | `xiaozhi-esp32-server/main/manager-api/src/main/java/xiaozhi/modules/knowledge/rag/impl/RAGFlowAdapter.java` | 与 RAGFlow API 的对接 |
| 6 | `xiaozhi-esp32-server/main/xiaozhi-server/plugins_func/functions/search_from_ragflow.py` | 对话检索请求与片段处理 |
| 7 | `xiaozhi-esp32-server/main/xiaozhi-server/core/connection.py` | 检索片段如何加入回答链路 |
| 8 | `FlutterClient/active/source-code/lib/services/`、`xiaozhi-esp32-main/main/protocols/` | 两种客户端如何连接服务端 |

本包提供代码，不包含 RAGFlow 线上库、实际文档和模型权重。如何登录智控台、上传文档及关联智能体见包根 `智控台操作指南.md`。服务器登录方法见 `服务器操作指南.md`，账号已确定为 `devuser`，密码只在服务器指南开头填写；实际权限由负责人确认。
