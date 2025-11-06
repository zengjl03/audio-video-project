import os
from pathlib import Path
from dotenv import load_dotenv
from core.pipeline.normal_processor import NormalProcessor
from core.pipeline.parallel_processor import ParallelProcessor
from core.utils import Config, TranscriptionLocalModelConfig, AnalyzerLocalModelConfig,AnalyzerAPIModelConfig

load_dotenv()

if __name__ == "__main__":
    from loguru import logger
    from init import setup
    # 初始化
    setup()

    # config = Config(
    #     video_path="video/test1.mp4",
    #     transcription_config=TranscriptionLocalModelConfig(model_name="paraformer-zh"),
    #     analyzer_config=AnalyzerLocalModelConfig(model_name="qwen3-4b"),
    #     output_dir=os.getenv("OUTPUT_DIR")
    # )

    # processor = NormalProcessor(config)
    # processor.process()


    config = Config(
        video_path="video/合成.mp4",
        transcription_config=TranscriptionLocalModelConfig(model_name="paraformer-zh"),
        analyzer_config=AnalyzerAPIModelConfig(model_name="gpt-4o-mini",
                                            base_url=os.getenv("BASE_URL"),
                                            api_key=os.getenv("API_KEY")),
        output_dir=os.getenv("OUTPUT_DIR"),

        segment_duration_minutes=5,
        max_workers=10,
        temp_dir=os.getenv("TMP_DIR")
    )

    processor = ParallelProcessor(config)
    processor.process()