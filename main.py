import os
from pathlib import Path
from dotenv import load_dotenv
from core.pipeline.parallel_processor import ParallelProcessor
from core.utils import AnalyzerPromptConfig, Config, TranscriptionLocalModelConfig, AnalyzerLocalModelConfig,AnalyzerAPIModelConfig,TranscriptionAPIModelConfig

load_dotenv()

if __name__ == "__main__":
    from init import setup
    # 初始化
    video_path = Path("video/微信视频_20251127150910.mp4")
    setup(video_path)

    config = Config(
        # transcription_config=TranscriptionLocalModelConfig(model_name="paraformer-zh"),
        transcription_config=TranscriptionAPIModelConfig(),
        analyzer_config=AnalyzerAPIModelConfig(
            model_name='gpt-5-mini',
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

    names,descs = processor.process(video_path)