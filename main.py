import os
from pathlib import Path
from dotenv import load_dotenv
from core.pipeline.parallel_processor import ParallelProcessor
from core.utils import AnalyzerPromptConfig, Config, TranscriptionLocalModelConfig, AnalyzerLocalModelConfig,AnalyzerAPIModelConfig,TranscriptionAPIModelConfig

load_dotenv()

if __name__ == "__main__":
    from init import setup
    # 初始化
    setup()
    # 并行处理存在视频裁剪问题

    # model_name = 'gpt-4.1-nano-2025-04-14'

    config = Config(
        video_path="video/test40.mp4",
        transcription_config=TranscriptionLocalModelConfig(model_name="paraformer-zh"),
        analyzer_config=AnalyzerAPIModelConfig(
            model_name="gpt-4o-mini",
            base_url=os.getenv("BASE_URL"),
            api_key=os.getenv("API_KEY"),
            prompt_config=AnalyzerPromptConfig(
                outline_prompt=Path('core/prompts/outline_prompt.txt'),
                highlight_prompt=Path('core/prompts/highlight_prompt.txt')
                )
        ),

        output_dir=os.getenv("OUTPUT_DIR"),
        segment_duration_minutes=30
    )

    processor = ParallelProcessor(config)
    processor.process()