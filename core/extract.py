import logging
from pathlib import Path
from moviepy.editor import VideoFileClip

from loguru import logger
from pydub import AudioSegment

class EditorManager:
    def __init__(self,video_path):
        self.video_path = video_path
    def extract_audio(self, audio_dir=None) -> Path | None:
        try:
            video_path = Path(self.video_path)
            if audio_dir is None:
                audio_dir = Path(__file__).resolve().parent.parent / "audio"
            else:
                audio_dir = Path(audio_dir)
            audio_dir.mkdir(parents=True, exist_ok=True)
            audio_path = audio_dir / f"{video_path.stem}.wav"
            if audio_path.exists():
                logger.info(f"Audio already exists: {audio_path}")
                return str(audio_path)
            with VideoFileClip(str(video_path)) as video_clip:
                if video_clip.audio is None:
                    logger.error(f"No audio in video: {video_path}")
                    return None

                temp_path = audio_dir / f"{video_path.stem}_temp.wav"
                video_clip.audio.write_audiofile(str(temp_path), logger=None)
                audio = AudioSegment.from_wav(temp_path)
                audio = audio.set_channels(1)  # 转为单声道
                audio.export(audio_path, format="wav")  # 覆盖原路径
                
                temp_path.unlink()  # 删除临时文件
                logger.info(f"Extracted: {audio_path}")
            return str(audio_path)
        except Exception as e:
            logger.error(f"Extract error: {e}")
            
    def crop_video(self, output_path, start, end):
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with VideoFileClip(str(self.video_path)) as video:
                cropped_video = video.subclip(start, end)
                cropped_video.write_videofile(str(output_path), codec='libx264')
            logger.info(f"Cropped: {output_path}")
        except Exception as e:
            logger.error(f"Crop error: {e}")

if __name__ == "__main__":
    editor = EditorManager("../video/test2.mp4")
    editor.extract_audio()
