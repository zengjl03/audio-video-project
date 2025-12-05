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
                # return str(audio_path)
            temp_audio = audio_dir / f"{video_path.stem}_temp.m4a"
            cmd1 = [
                'ffmpeg',
                '-i', str(video_path),  # 双引号包裹路径，兼容中文/空格
                '-vn',                    # 只提音频
                '-c:a', 'copy',           # 无损复制
                '-copyts',                # 保留原时间戳（防极端情况截断）
                '-avoid_negative_ts', 'make_zero',  # 修复负时间戳
                '-y',
                str(temp_audio)
            ]
            subprocess.run(cmd1, shell=False, check=True, stdout=subprocess.DEVNULL,  # 屏蔽标准输出
                           stderr=subprocess.DEVNULL)   # 屏蔽错误输出（ffmpeg日志主要走stderr）

            # 第二步：转码为单声道16k PCM（绝对兼容）
            sample_rate = 16000
            cmd2 = [
                'ffmpeg',
                '-i', str(temp_audio),
                '-ac', '1',                      # 单声道
                '-ar', str(sample_rate),         # 16k采样率
                '-c:a', 'pcm_s16le',             # WAV编码（无压缩，全兼容）
                '-af', 'aresample=async=1:min_hard_comp=0.1',  # 更鲁棒的重采样
                '-fflags', '+genpts',            # 重新生成时间戳
                '-y',
                str(audio_path)
            ]
            subprocess.run(cmd2, shell=False, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 清理临时文件（可选）
            import os
            if os.path.exists(temp_audio):
                os.remove(temp_audio)
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
            logger.info(cmd)
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
