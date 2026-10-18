import os
import io
import sys
import time
import shutil
import psutil
import asyncio

from funasr import AutoModel
from config.logger import setup_logging
from typing import Optional, Tuple, List
from core.providers.asr.utils import lang_tag_filter
from core.providers.asr.base import ASRProviderBase
from core.providers.asr.dto.dto import InterfaceType

TAG = __name__
logger = setup_logging()

MAX_RETRIES = 2
RETRY_DELAY = 1  # 重试延迟（秒）


# 捕获标准输出
class CaptureOutput:
    def __enter__(self):
        self._output = io.StringIO()
        self._original_stdout = sys.stdout
        sys.stdout = self._output

    def __exit__(self, exc_type, exc_value, traceback):
        sys.stdout = self._original_stdout
        self.output = self._output.getvalue()
        self._output.close()

        # 将捕获到的内容通过 logger 输出
        if self.output:
            logger.bind(tag=TAG).info(self.output.strip())


class ASRProvider(ASRProviderBase):
    def __init__(self, config: dict, delete_audio_file: bool):
        super().__init__()
        
        # 内存检测，要求大于2G
        min_mem_bytes = 2 * 1024 * 1024 * 1024
        total_mem = psutil.virtual_memory().total
        if total_mem < min_mem_bytes:
            logger.bind(tag=TAG).error(f"可用内存不足2G，当前仅有 {total_mem / (1024*1024):.2f} MB，可能无法启动FunASR")
        
        self.interface_type = InterfaceType.LOCAL
        self.model_dir = config.get("model_dir")
        self.output_dir = config.get("output_dir")  # 修正配置键名
        self.delete_audio_file = delete_audio_file

        # 热词配置 - 用于提升专业术语识别率
        self.hotword = config.get("hotword", "")

        # GPU 加速配置
        self.use_gpu = config.get("use_gpu", True)
        import torch
        if self.use_gpu and torch.cuda.is_available():
            self.device = "cuda:0"
            gpu_name = torch.cuda.get_device_name(0)
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            logger.bind(tag=TAG).info(f"FunASR GPU加速已启用: {gpu_name} ({gpu_mem:.1f}GB)")
        else:
            self.device = "cpu"
            logger.bind(tag=TAG).info("FunASR 使用CPU模式")

        # 确定模型来源 hub
        # iic/ 开头的模型来自 ModelScope，本地路径用 hf
        hub = "ms" if self.model_dir.startswith("iic/") else "hf"

        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
        logger.bind(tag=TAG).info(f"正在加载ASR模型: {self.model_dir} (hub={hub}, device={self.device})")
        with CaptureOutput():
            self.model = AutoModel(
                model=self.model_dir,
                vad_kwargs={"max_single_segment_time": 30000},
                disable_update=True,
                hub=hub,
                device=self.device,
            )
        
        if self.hotword:
            logger.bind(tag=TAG).info(f"热词已配置: {self.hotword[:50]}...")

    async def speech_to_text(
        self, opus_data: List[bytes], session_id: str, audio_format="opus", artifacts=None
    ) -> Tuple[Optional[str], Optional[str]]:
        """语音转文本主处理逻辑"""
        retry_count = 0
        
        while retry_count < MAX_RETRIES:
            try:
                if artifacts is None:
                    return "", None

                # 构建generate参数
                generate_kwargs = {
                    "input": artifacts.pcm_bytes,
                    "cache": {},
                    "language": "auto",
                    "use_itn": True,
                    "batch_size_s": 60,
                }
                # 添加热词（SeACo-Paraformer / Paraformer 热词版支持）
                if self.hotword:
                    generate_kwargs["hotword"] = self.hotword

                # 语音识别 - 使用线程池避免阻塞事件循环
                start_time = time.time()
                result = await asyncio.to_thread(
                    self.model.generate,
                    **generate_kwargs
                )

                # 兼容不同模型的返回格式：
                # SenseVoiceSmall: result[0] = {"text": "...", ...}
                # SeACo-Paraformer: result[0] 可能是字符串或 dict
                raw_result = result[0]
                if isinstance(raw_result, dict):
                    raw_text = raw_result.get("text", "")
                elif isinstance(raw_result, str):
                    raw_text = raw_result
                else:
                    logger.bind(tag=TAG).warning(f"未知的ASR返回格式: type={type(raw_result)}, value={raw_result}")
                    raw_text = str(raw_result)

                text = lang_tag_filter(raw_text)
                logger.bind(tag=TAG).info(
                    f"语音识别耗时: {time.time() - start_time:.3f}s | 原始结果: {raw_text} | 过滤后: {text}"
                )

                return text, artifacts.file_path

            except OSError as e:
                retry_count += 1
                if retry_count >= MAX_RETRIES:
                    logger.bind(tag=TAG).error(
                        f"语音识别失败（已重试{retry_count}次）: {e}", exc_info=True
                    )
                    return "", None
                logger.bind(tag=TAG).warning(
                    f"语音识别失败，正在重试（{retry_count}/{MAX_RETRIES}）: {e}"
                )
                time.sleep(RETRY_DELAY)

            except Exception as e:
                logger.bind(tag=TAG).error(f"语音识别失败: {e}", exc_info=True)
                return "", None
