import os
from pathlib import Path
from dotenv import load_dotenv
from core.pipeline.parallel_processor_v2 import ParallelProcessor_V2
from core.utils import AnalyzerModelNameConfig, AnalyzerPromptConfig, Config, TranscriptionLocalModelConfig, AnalyzerLocalModelConfig,AnalyzerAPIModelConfig,TranscriptionAPIModelConfig

load_dotenv()

if __name__ == "__main__":
    # 初始化
    # video_path = Path("video/微信视频2025-12-03_193819_529.mp4")
    video_path = Path("video/微信视频2025-12-08_131449_460.mp4")

    config = Config(
        # transcription_config=TranscriptionLocalModelConfig(model_name="paraformer-zh"),
        transcription_config=TranscriptionAPIModelConfig(),
        analyzer_config=AnalyzerAPIModelConfig(
            base_url=os.getenv("BASE_URL"),
            api_key=os.getenv("API_KEY"),
            model_name_config=AnalyzerModelNameConfig(
                # outline_model_name='gpt-5-nano-2025-08-07',
                outline_model_name='gpt-4.1',
                # highlight_model_name='gpt-4o-mini'
            ),
            prompt_config=AnalyzerPromptConfig(
                outline_prompt=Path('core/prompts/outline_v2.txt'),
                # highlight_prompt=Path('core/prompts/highlight_prompt.txt')
            )
        ),

        output_dir=os.getenv("OUTPUT_DIR"),
        segment_duration_minutes=30
    )

    processor = ParallelProcessor_V2(config)

    names,descs = processor.process(video_path)