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
from silero_vad import load_silero_vad, get_speech_timestamps
import librosa
import numpy as np
import soundfile as sf
import subprocess
import io
import argparse
import warnings
warnings.filterwarnings("ignore")
from core.utils import TranscriptionLocalModelConfig, TranscriptionAPIModelConfig, TranscriptionModel, Segment
torch.serialization.add_safe_globals([argparse.Namespace])
from loguru import logger

os.environ['HF_ENDPOINT'] = "https://hf-mirror.com"

# 全局常量（与参考代码一致）
WAV_SAMPLE_RATE = 16000
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
        res = self.model.generate(input=audio_path, batch_size_s=1200, hotword='哈哈哈')[0]
        sentence_info = res['sentence_info']
        return [Segment(text=seg['text'], start_time=seg['start'] / 1000, end_time=seg['end'] / 1000) for seg in sentence_info]


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


class SenseVoiceSmallModel(TranscriptionModel):
    def __init__(self):
        self.model = AutoModel(
            model="iic/SenseVoiceSmall",
            trust_remote_code=True,
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
            device="cuda:0"
        )

    def transcribe(self, audio_path: str) -> List[Segment]:
        res = self.model.generate(
            input=audio_path,
            cache={},
            language="zn",
            use_itn=True,
            batch_size_s=60,
            merge_vad=True,
            merge_length_s=15,
            ban_emo_unk=True
        )
        text = rich_transcription_postprocess(res[0]["text"])
        return [Segment(text=text, start_time=0.0, end_time=0.0)]

# TODO FireRedASRModel 暂时没有调整到位
class FireRedASRModel(TranscriptionModel):
    def __init__(self):
        from fireredasr.models.fireredasr import FireRedAsr
        self.model = FireRedAsr.from_pretrained("aed","FireRedTeam/FireRedASR-AED-L")

    def transcribe(self, audio_path: str) -> List[List[Any]]:
        def transcribe_parallel(audio_path, tmp_manager, model, decode_params):
            """并发执行两个转录任务"""
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                future1 = executor.submit(tmp_manager.transcribe, audio_path)
                logger.info('fireredasr transcribe start')
                future2 = executor.submit(model.transcribe, ['watrix'], [audio_path], decode_params)
                logger.info('fireredasr transcribe end')
                tmp_results = future1.result()
                fireredasr_results = future2.result()
            
            return tmp_results, fireredasr_results

        tmp_manager = TranscriptionManager(transcribe_mode="local", model_name="large-v3")

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

        # logger.info('aaaaresult',results)
        

        # tmp_results, fireredasr_results = transcribe_parallel(audio_path, tmp_manager, self.model, decode_params)
        # from core.llm import get_qwen_model
        # import ast
        # qwen_model = get_qwen_model()
        # from core.prompts.mixed_model_prompt import system_prompt
        # prompt = system_prompt.format(tmp_results=tmp_results, main_model_results=fireredasr_results)
        # logger.info(f'prompt: {prompt}')
        # response = qwen_model.chat(prompt=prompt,enable_thinking=False)
        # return ast.literal_eval(response['response'])

# 暂时弃用
class ApiTranscriptionModel(TranscriptionModel):
    def __init__(self):
        # 环境变量与配置参数
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("必须设置 DASHSCOPE_API_KEY 环境变量或通过 api_key 参数传入")
        
        self.num_threads = int(os.getenv("NUM_THREADS", 4))  # 添加默认值，避免KeyError
        self.segment_threshold = int(os.getenv("SEGMENT_THRESHOLD", 120))
        self.max_segment_threshold = int(os.getenv("MAX_SEGMENT_THRESHOLD", 180))

        self.min_silence_length = int(os.getenv("MIN_SILENCE_LEN", 500))  # 修正为length
        self.min_speech_length = int(os.getenv("MIN_SPEECH_LEN", 1500))
        self.temp_dir = Path(os.getenv("TMP_DIR") or str(Path.home() / "qwen3-asr-cache"))  # 修正为temp_dir
        self.temp_dir.mkdir(exist_ok=True)  # 创建临时目录
        
        # 加载Silero VAD模型
        self.vad_model = load_silero_vad()

    def _load_audio(self, file_path: str) -> np.ndarray:
        """加载音频文件，转为16kHz单声道"""
        try:
            if file_path.startswith(("http://", "https://")):
                raise ValueError("远程文件暂不支持，如需支持可扩展ffmpeg命令")
            
            # 优先用librosa加载（速度快）
            audio_data, _ = librosa.load(file_path, sr=WAV_SAMPLE_RATE, mono=True)
            return audio_data
        
        except Exception as e:
            print(f"librosa加载失败，使用ffmpeg备份方案：{e}")
            # ffmpeg备份方案：支持更多格式
            command = [
                'ffmpeg',
                '-i', file_path,
                '-ar', str(WAV_SAMPLE_RATE),
                '-ac', '1',  # 单声道
                '-c:a', 'pcm_s16le',
                '-f', 'wav',
                '-'  # 输出到标准输出
            ]
            
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False
            )
            stdout_data, stderr_data = process.communicate()
            
            if process.returncode != 0:
                raise RuntimeError(f"ffmpeg处理失败：{stderr_data.decode('utf-8', errors='ignore')}")
            
            # 读取ffmpeg输出的音频数据
            with io.BytesIO(stdout_data) as data_io:
                audio_data, _ = sf.read(data_io, dtype='float32')
            
            return audio_data

    def _process_vad(self, audio: np.ndarray) -> list[tuple[str, float, float]]:
        """基于Silero VAD拆分音频，返回[(片段路径, 起始时间秒, 结束时间秒), ...]"""
        try:
            # Silero VAD参数配置
            vad_params = {
                'sampling_rate': WAV_SAMPLE_RATE,
                'return_seconds': False,  # 返回采样点索引
                'min_speech_duration_ms': self.min_speech_length,  # 最小语音片段（1.5秒）
                'min_silence_duration_ms': self.min_silence_length  # 从配置读取最小静音时长
            }

            # 检测语音片段时间戳
            speech_timestamps = get_speech_timestamps(
                audio,
                self.vad_model,
                **vad_params
            )
            
            if not speech_timestamps:
                raise ValueError("VAD未检测到语音片段")

            # 1. 收集潜在拆分点（语音片段的起始/结束位置）
            potential_split_points = {0, len(audio)}  # 采样点索引
            for timestamp in speech_timestamps:
                potential_split_points.add(timestamp['start'])
                potential_split_points.add(timestamp['end'])
            
            sorted_potential_splits = sorted(potential_split_points)

            # 2. 按目标时长添加拆分点（避免片段过长）
            final_split_points = {0, len(audio)}
            segment_threshold_samples = self.segment_threshold * WAV_SAMPLE_RATE  # 目标时长（采样点）
            target_time = segment_threshold_samples
            
            while target_time < len(audio):
                # 找最接近目标时长的潜在拆分点（避免切断语音）
                closest_point = min(
                    sorted_potential_splits,
                    key=lambda p: abs(p - target_time)
                )
                final_split_points.add(closest_point)
                target_time += segment_threshold_samples
            
            final_ordered_splits = sorted(final_split_points)

            # 3. 确保片段不超过最大时长限制（强制拆分超长片段）
            new_split_points = [0]
            max_segment_samples = self.max_segment_threshold * WAV_SAMPLE_RATE  # 最大时长（采样点）
            
            for i in range(1, len(final_ordered_splits)):
                start_sample = final_ordered_splits[i-1]
                end_sample = final_ordered_splits[i]
                segment_length = end_sample - start_sample

                if segment_length <= max_segment_samples:
                    new_split_points.append(end_sample)
                else:
                    # 超长片段：平均拆分
                    num_subsegments = int(np.ceil(segment_length / max_segment_samples))
                    subsegment_length = segment_length // num_subsegments
                    
                    for j in range(1, num_subsegments):
                        new_split_points.append(start_sample + j * subsegment_length)
                    
                    new_split_points.append(end_sample)

            # 4. 生成最终片段（保存为wav文件，计算时间戳）
            chunk_info_list = []
            for i in range(len(new_split_points) - 1):
                start_sample = new_split_points[i]
                end_sample = new_split_points[i+1]
                
                # 提取音频片段
                audio_segment = audio[start_sample:end_sample]
                if len(audio_segment) == 0:
                    continue
                
                # 计算时间戳（秒）
                start_time = start_sample / WAV_SAMPLE_RATE
                end_time = end_sample / WAV_SAMPLE_RATE
                
                # 保存片段到临时目录
                temp_file_path = self.temp_dir / f"chunk_{start_time:.2f}_{end_time:.2f}.wav"
                sf.write(str(temp_file_path), audio_segment, WAV_SAMPLE_RATE)
                
                # 记录片段信息
                chunk_info_list.append((str(temp_file_path), round(start_time, 2), round(end_time, 2)))

            print(f"Silero VAD拆分完成：共 {len(chunk_info_list)} 段，总时长 {len(audio)/WAV_SAMPLE_RATE:.2f} 秒")
            return chunk_info_list

        except Exception as e:
            print(f"VAD分段失败，使用备用方案（按最大时长强制拆分）：{e}")
            # 备用方案：不依赖VAD，直接按最大时长拆分
            chunk_info_list = []
            total_samples = len(audio)
            max_chunk_samples = self.max_segment_threshold * WAV_SAMPLE_RATE
            
            for start_sample in range(0, total_samples, max_chunk_samples):
                end_sample = min(start_sample + max_chunk_samples, total_samples)
                audio_segment = audio[start_sample:end_sample]
                
                start_time = start_sample / WAV_SAMPLE_RATE
                end_time = end_sample / WAV_SAMPLE_RATE
                
                temp_file_path = self.temp_dir / f"chunk_{start_time:.2f}_{end_time:.2f}.wav"
                sf.write(str(temp_file_path), audio_segment, WAV_SAMPLE_RATE)
                
                chunk_info_list.append((str(temp_file_path), round(start_time, 2), round(end_time, 2)))
            
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
        WhisperLargeV3Model.__init__(self)
        # 显式初始化第二个父类
        ApiTranscriptionModel.__init__(self)

    def transcribe(self, audio_path: str) -> List[Segment]:
        audio_data = self._load_audio(audio_path)
        chunk_info_list = self._process_vad(audio_data)

        results = self._transcribe_chunks_parallel(chunk_info_list)
        qwen_result = ",".join([result[2] for result in results])
        segments, _ = self.model.transcribe(
            audio_path,
            language="zh",
            initial_prompt=qwen_result
        )
        return [Segment(text=seg.text, start_time=seg.start, end_time=seg.end) for seg in segments]

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
        