import os
import subprocess
import json
from pathlib import Path
from typing import List, Tuple, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
from loguru import logger
from dotenv import load_dotenv
from core.pipeline.base import PipelineProcessor
from core.utils import Config, timer
from core.utils import TranscriptionLocalModelConfig, TranscriptionAPIModelConfig, AnalyzerLocalModelConfig, AnalyzerAPIModelConfig

load_dotenv()


def _process_segment_worker(
    segment_path: Path,
    original_start: float,
    segment_index: int,
    transcription_config: TranscriptionLocalModelConfig | TranscriptionAPIModelConfig,
    analyzer_config: AnalyzerLocalModelConfig | AnalyzerAPIModelConfig
) -> List[dict]:
    """
    处理单个视频分段（提取精彩片段）- 独立工作函数
    
    注意：这个函数会在独立进程中运行，需要导入所有必要的模块
    """
    try:
        from core.extract import EditorManager
        from core.transcription import TranscriptionManager
        from core.highlight import AnalyzerManager
        from loguru import logger
        
        logger.info(f"[进程 {segment_index+1}] 开始处理分段: {segment_path.name}")
        
        # 1. 音频提取
        editor = EditorManager(segment_path)
        audio_path = editor.extract_audio()
        if not audio_path:
            logger.error(f"[进程 {segment_index+1}] 音频提取失败")
            return []
        
        # 2. 重建配置对象并创建转写器
        transcriber = TranscriptionManager(transcription_config)
        segments = transcriber.transcribe(audio_path)
        if not segments:
            logger.error(f"[进程 {segment_index+1}] 音频转写失败")
            return []

        logger.info(f"segments: {segments}")
        logger.info(f"转写完成，获取到{len(segments)}个片段: {segment_path.name}")
        
        # 3. 拼接带时间文本
        trans_text = ' '.join([f"[{start} - {end}] {text}\n" for text, start, end in segments])
        
        # 4. 大模型分析精彩片段
        highlighter = AnalyzerManager(analyzer_config)
        highlights = highlighter.analyze(trans_text)
        
        # 5. 调整时间戳：将分段内的时间戳转换为原始视频的时间戳
        adjusted_highlights = []
        for highlight in highlights:
            adjusted_highlight = highlight.copy()
            adjusted_highlight['start'] = highlight.get('start', 0) + original_start
            adjusted_highlight['end'] = highlight.get('end', 0) + original_start
            adjusted_highlight['segment_index'] = segment_index + 1
            adjusted_highlights.append(adjusted_highlight)
        
        logger.info(f"[进程 {segment_index+1}] 处理完成，提取到 {len(adjusted_highlights)} 个精彩片段")
        return adjusted_highlights
        
    except Exception as e:
        logger.error(f"[进程 {segment_index+1}] 处理分段时发生错误: {e}", exc_info=True)
        return []


class ParallelProcessor(PipelineProcessor):
    """并行视频处理器：将长视频按时间段分割，并行处理每个分段"""
    
    def __init__(self, config: Config):
        self.video_path = Path(config.video_path)
        self.transcriber_config = config.transcription_config
        self.analyzer_config = config.analyzer_config    
        self.editor = None  # 在 process 中按需创建
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        if not hasattr(config, 'segment_duration_minutes') and not hasattr(config, 'max_workers') and not hasattr(config, 'temp_dir'):
            raise ValueError("segment_duration_minutes, max_workers, temp_dir 不能为空")
        # 并行处理配置
        self.segment_duration_seconds = int(config.segment_duration_minutes) * 60
        self.max_workers = int(config.max_workers)
        self.temp_dir = Path(config.temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_video_duration(self, video_path: Path) -> float:
        """获取视频总时长（秒）"""
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', str(video_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(json.loads(result.stdout)['format']['duration'])
        logger.info(f"视频 {video_path.name} 总时长: {duration/60:.2f}分钟")
        return duration
    
    def _split_video(self, video_path: Path) -> List[Tuple[Path, float, float]]:
        """将视频分割成多个分段"""
        duration = self._get_video_duration(video_path)
        num_segments = int(duration / self.segment_duration_seconds) + (1 if duration % self.segment_duration_seconds > 0 else 0)
        logger.info(f"视频将分割为 {num_segments} 个分段，每段约 {self.segment_duration_seconds/60:.1f} 分钟")
        
        segments = []
        for i in range(num_segments):
            start_time = i * self.segment_duration_seconds
            end_time = min((i + 1) * self.segment_duration_seconds, duration)
            segment_path = self.temp_dir / f"{video_path.stem}_segment_{i+1:03d}.mp4"
            
            cmd = ['ffmpeg', '-ss', str(start_time), '-to', str(end_time), '-i', str(video_path),
                   '-c:v', 'copy', '-c:a', 'copy', '-avoid_negative_ts', 'make_zero', '-y', str(segment_path)]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            segments.append((segment_path, start_time, end_time))
            logger.info(f"分段 {i+1}/{num_segments} 切割完成")
        
        return segments
    
    @timer
    def process(self):
        # 检查
        if not self.check_video(self.video_path):
            return
        logger.info(f"开始并行处理视频: {self.video_path}")
        # 1. 分割视频
        segments = self._split_video(self.video_path)
        if not segments:
            logger.error("视频分割失败，没有生成任何分段")
            return
        
        # 2. 并行处理每个分段
        logger.info(f"开始并行处理 {len(segments)} 个分段，使用 {self.max_workers} 个进程")
        all_highlights = []
        
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_segment = {
                executor.submit(_process_segment_worker, seg_path, original_start, idx, 
                               self.transcriber_config, self.analyzer_config): idx
                for idx, (seg_path, original_start, _) in enumerate(segments)
            }
            
            segment_results = {}
            for future in as_completed(future_to_segment):
                idx = future_to_segment[future]
                try:
                    highlights = future.result()
                    segment_results[idx] = highlights
                    logger.info(f"分段 {idx+1} 处理完成，获得 {len(highlights)} 个精彩片段")
                except Exception as e:
                    logger.error(f"分段 {idx+1} 处理失败: {e}", exc_info=True)
                    segment_results[idx] = []
            
            # 按顺序合并结果
            for idx in sorted(segment_results.keys()):
                all_highlights.extend(segment_results[idx])
        
        # 3. 按时间戳排序
        all_highlights.sort(key=lambda x: x.get('start', 0))
        
        logger.info(f"分析完成，获取到{len(all_highlights)}个精彩片段: {self.video_path}")
        if not all_highlights:
            logger.warning(f"未提取到精彩片段: {self.video_path}")
            return
        
        # 4. 保存精彩片段
        from core.extract import EditorManager
        editor = EditorManager(self.video_path)
        for idx, clip in enumerate(all_highlights, 1):
            outname = f"clip_{self.video_path.stem}_{idx:02d}.mp4"
            outpath = self.output_dir / outname
            editor.crop_video(outpath, clip.get('start'), clip.get('end'))
            logger.info(f"已保存精彩片段: {outpath}")
        
        # 5. 清理临时分段文件
        for seg_path, _, _ in segments:
            try:
                if seg_path.exists():
                    seg_path.unlink()
            except Exception as e:
                logger.warning(f"删除临时文件失败 {seg_path}: {e}")



