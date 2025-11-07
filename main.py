import os
from pathlib import Path
from dotenv import load_dotenv
from core.pipeline.normal_processor import NormalProcessor
from core.pipeline.parallel_processor import ParallelProcessor
from core.utils import Config, TranscriptionLocalModelConfig, AnalyzerLocalModelConfig,AnalyzerAPIModelConfig,TranscriptionAPIModelConfig

load_dotenv()

if __name__ == "__main__":
    from init import setup
    # 初始化
    setup()

    # config = Config(
    #     video_path="video/f4e087102a12aab1a49d1759e3429b31.mp4",
    #     transcription_config=TranscriptionAPIModelConfig(),
    #     analyzer_config=AnalyzerAPIModelConfig(model_name="gpt-4o-mini",
    #                                         base_url=os.getenv("BASE_URL"),
    #                                         api_key=os.getenv("API_KEY")),
    #     output_dir=os.getenv("OUTPUT_DIR")
    # )

    config = Config(
        video_path="video/f4e087102a12aab1a49d1759e3429b31.mp4",
        # transcription_config=TranscriptionAPIModelConfig(),
        transcription_config=TranscriptionLocalModelConfig(model_name="large-v3"),
        analyzer_config=AnalyzerAPIModelConfig(model_name="gpt-5-mini",
                                            base_url=os.getenv("BASE_URL"),
                                            api_key=os.getenv("API_KEY")),
        # analyzer_config=AnalyzerLocalModelConfig(model_name="qwen3-4b"),
        output_dir=os.getenv("OUTPUT_DIR"),
    )

    processor = NormalProcessor(config)
    processor.process()


    # 并行处理存在视频裁剪问题

    # model_name = 'gpt-4.1-nano-2025-04-14'

    # config = Config(
    #     video_path="video/特别版-上.mp4",
    #     transcription_config=TranscriptionLocalModelConfig(model_name="paraformer-zh"),
    #     analyzer_config=AnalyzerAPIModelConfig(model_name="gpt-5-mini",
    #                                         base_url=os.getenv("BASE_URL"),
    #                                         api_key=os.getenv("API_KEY")),
    #     output_dir=os.getenv("OUTPUT_DIR"),

    #     segment_duration_minutes=30,
    #     max_workers=10,
    #     temp_dir=os.getenv("TMP_DIR")
    # )

    # processor = ParallelProcessor(config)
    # processor.process()