from faster_whisper import WhisperModel
from funasr import AutoModel
import torch
from typing import Literal, List, Any, Optional, Tuple
import os
from abc import ABC, abstractmethod
from funasr.utils.postprocess_utils import rich_transcription_postprocess
from dotenv import load_dotenv
from pathlib import Path
import dashscope
from pydub import AudioSegment
import soundfile as sf
import argparse
import warnings
warnings.filterwarnings("ignore")
from core.utils import TranscriptionLocalModelConfig, TranscriptionAPIModelConfig, TranscriptionModel, Segment, SegmentWithSpk
torch.serialization.add_safe_globals([argparse.Namespace])
from loguru import logger

os.environ['HF_ENDPOINT'] = "https://hf-mirror.com"

load_dotenv()

class ParaformerZhModel(TranscriptionModel):
    def __init__(self):
        self.model = AutoModel(
            model="paraformer-zh",
            vad_model="fsmn-vad",
            punc_model="ct-punc",
            spk_model="cam++",
            device="cuda",
            disable_update=True
        )

    def transcribe(self, audio_path: str) -> List[Segment]:
        res = self.model.generate(input=audio_path, batch_size_s=600, hotword='哈哈哈')[0]
        sentence_info = res['sentence_info']
        return [SegmentWithSpk(text=seg['text'], start_time=seg['start'] / 1000, end_time=seg['end'] / 1000, spk_id=seg['spk']) for seg in sentence_info]

class WhisperLargeV3Model(TranscriptionModel):
    def __init__(self):
        self.model = WhisperModel(
            "large-v3",
            device="cuda" if torch.cuda.is_available() else "cpu",
            local_files_only=True
        )

    def transcribe(self, audio_path: str) -> List[Segment]:
        segments, _ = self.model.transcribe(
            audio_path,
            language="zh",
            no_speech_threshold=0.7           # 避免误判笑声为静音
        )
        # logger.info(f'WhisperLargeV3Model transcribe segments: {list(segments)}')
        return [Segment(text=segment.text, start_time=segment.start, end_time=segment.end) for segment in segments]

# 与ParaformerZhModel效果差不多，并且无法引入spk_id，暂时弃用
class SenseVoiceSmallModel(TranscriptionModel):
    def __init__(self):
        self.model = AutoModel(
            model="iic/SenseVoiceSmall",
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
            device="cuda:0",
            disable_update=True
        )

    def transcribe(self, audio_path: str) -> List[Segment]:
        res = self.model.generate(
            input=audio_path,
            cache={},
            language="zh",
            use_itn=True,
            batch_size_s=60,
            merge_vad=False,
            # merge_length_s=15,
            ban_emo_unk=True
        )
        text = rich_transcription_postprocess(res[0]["text"])
        # print(text)

# FireRedASRModel 经测试占用显存和时间都很大，暂时弃用
class FireRedASRModel(TranscriptionModel):
    def __init__(self):
        from fireredasr.models.fireredasr import FireRedAsr
        self.model = FireRedAsr.from_pretrained("aed","FireRedTeam/FireRedASR-AED-L")

    def transcribe(self, audio_path: str) -> List[List[Any]]:
        decode_params = {
            "use_gpu": 1,
            "beam_size": 3,
            "nbest": 1,
            "decode_max_len": 0,
            "softmax_smoothing": 1.0,
            "aed_length_penalty": 0.0,
            "eos_penalty": 1.0
        }
        results = self.model.transcribe(
            ['watrix'],
            [audio_path],
            decode_params
        )
        print(results)

# 暂时弃用
class ApiTranscriptionModel(TranscriptionModel):
    def __init__(self):
        # 环境变量与配置参数
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("必须设置 DASHSCOPE_API_KEY 环境变量或通过 api_key 参数传入")
        
        self.num_threads = int(os.getenv("NUM_THREADS", 4))  # 添加默认值，避免KeyError
        self.temp_dir = Path(os.getenv("TMP_DIR") or str(Path.home() / "qwen3-asr-cache"))  # 修正为temp_dir
        self.temp_dir.mkdir(exist_ok=True)  # 创建临时目录
        
        
    def _process_vad(self, audio: str) -> List[Tuple[str, float, float]]:
        
        vad_model = AutoModel(model="fsmn-vad", model_revision="v2.0.4",disable_update=True) 
        vad_result = vad_model.generate(input=audio)[0].get('value',[])
        # 提取音频片段
        audio_s = AudioSegment.from_file(audio)
        # 4. 生成最终片段（保存为wav文件，计算时间戳）
        chunk_info_list = []
        for start,end in vad_result:
            audio_segment = audio_s[start:end]
            # 计算时间戳（秒）
            start_time = start / 1000
            end_time = end / 1000

            # 保存片段到临时目录
            temp_file_path = self.temp_dir / f"chunk_{start_time:.2f}_{end_time:.2f}.wav"
            audio_segment.export(temp_file_path, format="wav")  # 可根据需要改为 "mp3" 等格式
            # 记录片段信息
            chunk_info_list.append((str(temp_file_path), round(start_time, 2), round(end_time, 2)))

        print(f"VAD拆分完成：共 {len(chunk_info_list)} 段")
        return chunk_info_list

    def _transcribe_single_chunk(self, chunk_info: Tuple[str, float, float]) -> Segment:
        """转录单个音频片段，返回(起始时间, 结束时间, 转录文本)"""
        chunk_path, start_time, end_time = chunk_info
        
        try:
            messages = [
                {"role": "system", "content": [{"text": ""}]},
                {"role": "user", "content": [{"audio": chunk_path}]}
            ]
            
            response = dashscope.MultiModalConversation.call(
                api_key=self.api_key,
                model="qwen3-asr-flash",
                messages=messages,
                result_format="message",
                asr_options={"language": "zh", "enable_itn": False, "enable_lid": True}
            )
            
            if response.status_code != 200:
                raise Exception(f"HTTP状态码异常: {response.status_code} {response}")
            
            output = response['output']['choices'][0]
            recognized_text = None
            
            if len(output["message"]["content"]):
                recognized_text = output["message"]["content"][0]["text"]
            
            # 确保返回非None值
            recognized_text = recognized_text.strip() if recognized_text else ""
            return Segment(text=recognized_text, start_time=start_time, end_time=end_time)
        
        except Exception as e:
            print(f"片段转录失败（{start_time:.2f}-{end_time:.2f}）：{e}")
            return Segment(text="", start_time=start_time, end_time=end_time)

    def _transcribe_chunks_parallel(self, chunk_info_list: List[Tuple[str, float, float]]) -> List[Segment]:
        """
        并发转录所有音频片段
        :param chunk_info_list: 片段信息列表 [(片段路径, 起始时间, 结束时间), ...]
        :return: 转录结果列表 [(起始时间, 结束时间, 转录文本), ...]
        """
        import concurrent.futures
        from tqdm import tqdm
        
        if not chunk_info_list:
            return []
        
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            future_to_chunk = {
                executor.submit(self._transcribe_single_chunk, chunk_info): chunk_info
                for chunk_info in chunk_info_list
            }
            
            for future in tqdm(
                concurrent.futures.as_completed(future_to_chunk),
                total=len(chunk_info_list),
                desc="API并发转录片段中"
            ):
                results.append(future.result())
        
        # 按起始时间排序（确保顺序正确）
        results.sort(key=lambda x: x.start_time)
        return results

class ApiTranscriptionModel_V2(WhisperLargeV3Model,ApiTranscriptionModel):
    def __init__(self):
        # 显式初始化第一个父类
        # WhisperLargeV3Model.__init__(self)
        # 显式初始化第二个父类
        ApiTranscriptionModel.__init__(self)

    def transcribe(self, audio_path: str) -> List[Segment]:
        chunk_info_list = self._process_vad(audio_path)
        # print(chunk_info_list)
        segments = self._transcribe_chunks_parallel(chunk_info_list)
        # print('qwen_result: ', qwen_result)
        # segments, _ = self.model.transcribe(
        #     audio_path,
        #     language="zh",
        #     # initial_prompt=qwen_result
        # )
        # print('segments: ', [Segment(text=seg.text, start_time=seg.start, end_time=seg.end) for seg in segments])
        # import shutil
        # shutil.rmtree(self.temp_dir, ignore_errors=True)
        for it in chunk_info_list:
            path,_,_ = it
            Path(path).unlink(missing_ok=False)
        return [Segment(text=seg.text, start_time=seg.start_time, end_time=seg.end_time) for seg in segments]

class LocalModelFactory:
    @staticmethod
    def create_model(model_name: Literal["paraformer-zh", "large-v3", "sense-voice-small", "firered-asr"]) -> TranscriptionModel:
        """根据模型名创建对应的本地模型实例"""
        model_map = {
            "paraformer-zh": ParaformerZhModel,
            "large-v3": WhisperLargeV3Model,
            "sense-voice-small": SenseVoiceSmallModel,
            "firered-asr": FireRedASRModel
        }
        if model_name not in model_map:
            raise ValueError(f"不支持的模型名: {model_name}")
        return model_map[model_name]()

class TranscriptionManager:
    def __init__(
        self,
        config: TranscriptionLocalModelConfig | TranscriptionAPIModelConfig
    ):
        self.transcribe_mode = config.mode
        self.transcriber: TranscriptionModel

        if isinstance(config, TranscriptionLocalModelConfig):
            if not config.model_name:
                raise ValueError("本地模式必须指定model_name")
            self.transcriber = LocalModelFactory.create_model(config.model_name)
        elif isinstance(config, TranscriptionAPIModelConfig):
            self.transcriber = ApiTranscriptionModel_V2()

    def transcribe(self, audio_path: str) -> List[Segment]:
        """对外提供的转写接口，统一调用方式"""
        return self.transcriber.transcribe(audio_path)
        