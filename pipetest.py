import os
import time
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

# 加载环境变量并配置HF镜像
load_dotenv()
os.environ['HF_ENDPOINT'] = "https://hf-mirror.com"

from init import setup_logger
from core.pipeline.normal_processor import normal_processor
from core.pipeline.parallel_processor import ParallelVideoProcessor

if __name__ == "__main__":
    setup_logger()

    # 待处理的视频文件名（自动添加.mp4后缀）
    # base_filenames = [
    #     "test1", "test3", "test5", "test6", "test7", 
    #     "test8", "test9", "test15", "test17", 
    #     "test22", "test28", "test31", "test37"
    # ]
    base_filenames = [
        "特别版-上"
    ]
    # 为所有文件名添加.mp4后缀
    video_filenames = [f"{name}.mp4" for name in base_filenames]
    
    # 视频文件所在目录（默认为video文件夹）
    video_dir = Path("video")
    video_dir.mkdir(exist_ok=True)

    # 批量处理视频
    total_start = time.time()
    logger.info(f"开始批量处理，共{len(video_filenames)}个MP4文件")

    # 选择处理模式：'parallel' 使用并行处理（推荐用于长视频），'normal' 使用原始串行处理
    use_parallel = os.getenv("USE_PARALLEL_PROCESSING", "false").lower() == "true"
    
    for filename in video_filenames:
        video_path = video_dir / filename
        
        if use_parallel:
            # 使用并行处理模式
            logger.info(f"使用并行处理模式处理视频: {video_path}")
            processor = ParallelVideoProcessor()
            highlights = processor.process_video_parallel(video_path)
            logger.info(f"并行处理完成，共提取 {len(highlights)} 个精彩片段")
        else:
            # 使用原始串行处理模式
            pipeline(video_path)
        
        # 处理完一个视频后稍作停顿，避免资源占用过高
        time.sleep(1)
        logger.info("----------------------------------------------------------")
        # break

    total_time = time.time() - total_start
    logger.info(f"所有视频处理完毕，总耗时{total_time:.2f}秒")
    logger.info(f"完整日志已保存至: {log_file}")