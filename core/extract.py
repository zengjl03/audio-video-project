from pathlib import Path
from moviepy.editor import VideoFileClip
from loguru import logger
import subprocess

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
            cmd = [
                'ffmpeg', '-i', str(video_path),
                '-ac', '1',  # 转为单声道
                '-y',  # 覆盖输出文件
                str(audio_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=False)  # 不自动解码，避免编码问题
            if result.returncode != 0:
                logger.error(f"FFmpeg 错误: {result.stderr.decode('gbk', errors='replace')}")
            logger.info(f"Extracted: {audio_path}")
            return str(audio_path)
        except Exception as e:
            logger.error(f"Extract error: {e}")
            
    def crop_video(self, output_path, start, end):
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            cmd = [
                'ffmpeg',
                '-ss', str(start),       # 开始时间
                '-to', str(end),         # 结束时间
                '-i', str(self.video_path),  # 输入文件
                '-c:v', 'copy',          # 视频流直接复制（不重新编码，避免编码器问题）
                '-c:a', 'copy',          # 音频流直接复制
                '-copyts',               # 保留时间戳
                '-y',                    # 覆盖输出
                str(output_path)
            ]
            
            # 执行命令，忽略输出避免编码问题
            subprocess.run(
                cmd, 
                check=True, 
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            logger.info(f"Cropped: {output_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg crop error (return code {e.returncode})")
            raise e
        except Exception as e:
            logger.error(f"Crop error: {e}")
            raise e

if __name__ == "__main__":
    editor = EditorManager("../video/test2.mp4")
    editor.extract_audio()
