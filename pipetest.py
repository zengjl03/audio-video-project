import os
from pathlib import Path
from dotenv import load_dotenv
from core.pipeline.parallel_processor_v2 import ParallelProcessor_V2
from core.utils import AnalyzerModelNameConfig
from core.utils import AnalyzerPromptConfig, Config, TranscriptionLocalModelConfig, AnalyzerLocalModelConfig,AnalyzerAPIModelConfig,TranscriptionAPIModelConfig

load_dotenv()

if __name__ == "__main__":
    config = Config(
        # transcription_config=TranscriptionLocalModelConfig(model_name="paraformer-zh"),
        transcription_config=TranscriptionAPIModelConfig(),
        analyzer_config=AnalyzerAPIModelConfig(
            base_url=os.getenv("BASE_URL"),
            api_key=os.getenv("API_KEY"),
            model_name_config=AnalyzerModelNameConfig(
                # outline_model_name='gpt-5-nano-2025-08-07',
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

    # path_list = list(Path('video_local').glob('*.mp4'))
    base_dir = Path('video_local')
    # path_list = [base_dir / f'test{i}.mp4' for i in range(30,38+1)]
    path_list = [base_dir / '跆拳道打卡第7天_20251229175320.mp4',base_dir / '跆拳道打卡第19天c_20251229175506.mp4',base_dir / '跆拳道课打卡第21天_20251229175512.mp4']
    for i in path_list[:1]:
        print(f'正在处理: {i}')
        processor = ParallelProcessor_V2(config)
        names,descs = processor.process(i)