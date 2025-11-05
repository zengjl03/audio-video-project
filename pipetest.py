import os
import time
from pathlib import Path
from loguru import logger
from core.extract import EditorManager
from core.transcription import TranscriptionManager
from core.highlight import AnalyzerManager
from dotenv import load_dotenv
from init import setup

# 加载环境变量并配置HF镜像
load_dotenv()
os.environ['HF_ENDPOINT'] = "https://hf-mirror.com"

# 配置日志 - 同时输出到控制台和文件
def configure_logger():
    log_dir = Path("log")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"pipeline_test_{time.strftime('%Y%m%d_%H%M%S')}.log"
    
    # 移除默认日志配置，添加新配置
    logger.remove()
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level="INFO",
        rotation="10 MB",
        retention="7 days"
    )
    logger.add(
        lambda msg: print(msg, end=""),  # 同时输出到控制台
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level="INFO"
    )
    return log_file

def pipeline(video_path: Path):
    # 检查文件是否存在
    if not video_path.exists():
        logger.error(f"文件不存在: {video_path}")
        return
    
    # 强制检查是否为MP4格式
    if video_path.suffix.lower() != '.mp4':
        logger.warning(f"非MP4格式文件，跳过处理: {video_path}")
        return

    logger.info(f"开始处理视频: {video_path}")
    start_time = time.time()

    try:
        # 1. 音频提取
        editor = EditorManager(video_path)
        audio_path = editor.extract_audio()
        if not audio_path or not Path(audio_path).exists():
            logger.error(f"音频提取失败，跳过: {video_path}")
            return

        # 2. 音频转写
        # transcriber = TranscriptionManager(transcribe_mode="local", model_name="large-v3")
        transcriber = TranscriptionManager(transcribe_mode="local",model_name="paraformer-zh")
        # transcriber = TranscriptionManager(transcribe_mode="api")  # 备用API模式
        segments = transcriber.transcribe(audio_path)
        logger.info(f"segments: {segments}")
        logger.info(f"转写完成，获取到{len(segments)}个片段: {video_path}")
        if not segments:
            logger.error(f"音频转写失败，跳过: {video_path}")
            return

        # 3. 拼接带时间文本
        trans_text = ' '.join([f"[{start} - {end}] {text}\n" for text, start, end in segments])

        # 4. 大模型分析精彩片段
        highlighter = AnalyzerManager(mode='local')
        highlights = highlighter.analyze(trans_text)

        logger.info(f"分析完成，获取到{len(highlights)}个精彩片段: {video_path}")
        if not highlights:
            logger.warning(f"未提取到精彩片段: {video_path}")
            return

        # 5. 裁剪并保存精彩片段
        output_dir = Path(os.getenv("PROCESSED_DIR", 'processed'))
        output_dir.mkdir(exist_ok=True)
        
        for idx, clip in enumerate(highlights, 1):
            outname = f"clip_{video_path.stem}_{idx:02d}.mp4"
            outpath = output_dir / outname
            editor.crop_video(outpath, clip.get('start'), clip.get('end'))
            logger.info(f"已保存精彩片段: {outpath}")

        process_time = time.time() - start_time
        logger.success(f"视频处理完成，耗时{process_time:.2f}秒: {video_path}")

    except Exception as e:
        logger.error(f"处理视频时发生错误: {video_path}，错误信息: {str(e)}", exc_info=True)

if __name__ == "__main__":
    # 初始化配置
    setup()
    # 配置日志
    log_file = configure_logger()
    logger.info(f"日志文件已保存至: {log_file}")

    # 待处理的视频文件名（自动添加.mp4后缀）
    # base_filenames = [
    #     "test1", "test3", "test5", "test6", "test7", 
    #     "test8", "test9", "test15", "test17", 
    #     "test22", "test28", "test31", "test37"
    # ]
    base_filenames = [
        "testtutu"
    ]
    # 为所有文件名添加.mp4后缀
    video_filenames = [f"{name}.mp4" for name in base_filenames]
    
    # 视频文件所在目录（默认为video文件夹）
    video_dir = Path("video")
    video_dir.mkdir(exist_ok=True)

    # 批量处理视频
    total_start = time.time()
    logger.info(f"开始批量处理，共{len(video_filenames)}个MP4文件")

    for filename in video_filenames:
        video_path = video_dir / filename
        pipeline(video_path)
        # 处理完一个视频后稍作停顿，避免资源占用过高
        time.sleep(1)
        logger.info("----------------------------------------------------------")
        # break

    total_time = time.time() - total_start
    logger.info(f"所有视频处理完毕，总耗时{total_time:.2f}秒")
    logger.info(f"完整日志已保存至: {log_file}")