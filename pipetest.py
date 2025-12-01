import os
from pathlib import Path
from dotenv import load_dotenv
from core.pipeline.parallel_processor import ParallelProcessor
from core.utils import AnalyzerPromptConfig, Config, TranscriptionLocalModelConfig, AnalyzerLocalModelConfig,AnalyzerAPIModelConfig,TranscriptionAPIModelConfig

load_dotenv()

if __name__ == "__main__":
    for i in range(28,60+1):
        video_path = f"video/test{i}.mp4"
        config = Config(
            transcription_config=TranscriptionAPIModelConfig(),
            analyzer_config=AnalyzerAPIModelConfig(
                model_name='gemini-2.5-flash-nothinking',
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