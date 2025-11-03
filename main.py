import os
from glob import glob
from pathlib import Path
import subprocess
from core.extract import EditorManager
from core.transcription import TranscriptionManager
from core.highlight import AnalyzerManager
import logging
from dotenv import load_dotenv

load_dotenv()
os.environ['HF_ENDPOINT'] = "https://hf-mirror.com"

def pipeline(video_path: str):
    video_path = Path(video_path)
    logger.info(f"处理视频: {video_path}")

    # 1. 音频提取
    editor = EditorManager(video_path)
    audio_path = editor.extract_audio()
    if not audio_path:
        logger.error(f"音频提取失败，跳过: {video_path}")
        return

    # 2. 音频转写
    # transcriber = TranscriptionManager(transcribe_mode="local", model_name="firered-asr")
    transcriber = TranscriptionManager(transcribe_mode="api")
    segments = transcriber.transcribe(audio_path)
    logger.info(f'segments: {segments}')
    if not segments:
        logger.error(f"音频转写失败，跳过: {video_path}")
        return

    # 3. 拼接带时间文本
    trans_text = ''.join([f"[{start} - {end}] {text}\n" for text, start, end in segments])

    # 4. LLM/大模型分析精彩片段
    # highlighter = AnalyzerManager(mode='local')
    highlighter = AnalyzerManager(mode='local')
    highlights = highlighter.analyze(trans_text)

    logger.info(f'highlights: {highlights}')
    print(type(highlights))
    if not highlights:
        logger.error(f"未提取到精彩片段，跳过: {video_path}")
        return

    # 5. 批量裁剪高光片段
    for idx, clip in enumerate(highlights, 1):
        outname = f"clip_{video_path.stem}_{idx:02d}.mp4"
        outpath = Path(os.getenv("PROCESSED_DIR",'processed')) / outname
        editor.crop_video(outpath, clip.get('start'), clip.get('end'))
    logger.info(f"已处理完毕: {video_path}")

if __name__ == "__main__":
    # video_files = glob(os.path.join(video_dir, '*.mp4'))
    # for vfile in video_files:
    #     try:
    #         pipeline(vfile)
    #     except Exception as e:
    #         logger.error(f"处理{vfile}时发生异常: {e}")
    from loguru import logger
    from init import setup
    # 初始化
    setup()

    # subprocess.run(["python", "download.py"])

    video_path = "video/test14.mp4"
    pipeline(video_path)