import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import redis as redis_lib
from loguru import logger

from ..config import API_KEY, BASE_URL, LOG_DIR, OUTLINE_MODEL, REDIS_URL, RESULT_DIR, SEGMENT_DURATION_MINUTES
from .celery_app import celery_app
from .models import Task, db, get_current_prompt

BACKEND_ROOT = Path(__file__).resolve().parent.parent
_redis_client = redis_lib.from_url(REDIS_URL, decode_responses=True)
_ACTIVE_TASK_LOG_PATHS: dict[int, Path] = {}


class TaskCancelledError(Exception):
    """Raised when task is manually stopped from UI."""


def _task_log_prefix(task_id: int) -> str:
    return f"task_{task_id}_run_"


def _task_log_path(task_id: int) -> Path:
    logs = sorted(
        LOG_DIR.glob(f"{_task_log_prefix(task_id)}*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if logs:
        return logs[0]
    return LOG_DIR / f"task_{task_id}.log"


def _new_task_log_path(task_id: int) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return LOG_DIR / f"{_task_log_prefix(task_id)}{ts}.log"


def _task_log(task_id: int, level: str, message: str, log_path: Path | None = None) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    path = log_path or _ACTIVE_TASK_LOG_PATHS.get(task_id) or _task_log_path(task_id)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] [{level}] {message}\n")


def _emit_progress(
    task_id: int,
    progress: int,
    msg: str,
    status: str = "processing",
    log_path: Path | None = None,
) -> None:
    payload = json.dumps(
        {"task_id": task_id, "progress": progress, "msg": msg, "status": status},
        ensure_ascii=False,
    )
    _redis_client.publish("task_progress", payload)
    _task_log(task_id, "PROGRESS", f"{status} {progress}% {msg}", log_path=log_path)

    db.connect(reuse_if_open=True)
    try:
        task = Task.get_by_id(task_id)
        if status == "processing" and task.status == "failed" and "手动终止" in (task.progress_msg or ""):
            raise TaskCancelledError("task manually cancelled")
        task.progress = progress
        task.progress_msg = msg
        task.status = status
        task.save()
    finally:
        db.close()


def _save_result(task_id: int, clips: list[dict[str, Any]]) -> None:
    db.connect(reuse_if_open=True)
    try:
        task = Task.get_by_id(task_id)
        task.result_json = json.dumps(clips, ensure_ascii=False)
        task.save()
    finally:
        db.close()


def _run_video_pipeline(task_id: int) -> None:
    from core.extract import EditorManager
    from core.pipeline.parallel_processor_v2 import ParallelProcessor_V2
    from core.utils import (
        AnalyzerAPIModelConfig,
        AnalyzerModelNameConfig,
        AnalyzerPromptConfig,
        Config,
        EventItem,
        Segment,
        TranscriptionAPIModelConfig,
    )

    db.connect(reuse_if_open=True)
    try:
        task = Task.get_by_id(task_id)
        video_path = Path(task.file_path)
    finally:
        db.close()

    if not video_path.exists():
        _emit_progress(task_id, 0, f"视频文件不存在: {video_path}", "failed")
        return

    temp_prompt = Path(tempfile.mktemp(suffix=".txt", dir=str(BACKEND_ROOT)))
    temp_prompt.write_text(get_current_prompt(), encoding="utf-8")

    current_log_path = _new_task_log_path(task_id)
    _ACTIVE_TASK_LOG_PATHS[task_id] = current_log_path
    sink_id = logger.add(str(current_log_path), level="INFO", enqueue=False)
    _task_log(task_id, "INFO", f"task start: {video_path.name}")

    try:
        _emit_progress(task_id, 5, "初始化配置...", "processing")

        config = Config(
            transcription_config=TranscriptionAPIModelConfig(),
            analyzer_config=AnalyzerAPIModelConfig(
                base_url=BASE_URL,
                api_key=API_KEY,
                model_name_config=AnalyzerModelNameConfig(outline_model_name=OUTLINE_MODEL),
                prompt_config=AnalyzerPromptConfig(outline_prompt=temp_prompt),
            ),
            output_dir=str(RESULT_DIR),
            segment_duration_minutes=SEGMENT_DURATION_MINUTES,
        )

        class ProgressProcessor(ParallelProcessor_V2):
            def process(self, current_video_path: Path):
                self.video_path = current_video_path
                self.editor = EditorManager(self.video_path)
                names: list[str] = []
                descs: list[str] = []

                if not self.check_video(self.video_path):
                    _emit_progress(task_id, 0, "视频文件校验失败", "failed")
                    return names, descs

                _emit_progress(task_id, 10, "正在提取音频...", "processing")
                audio_path = self.editor.extract_audio()
                if not audio_path:
                    _emit_progress(task_id, 0, "音频提取失败", "failed")
                    return names, descs

                self.audio_path = audio_path
                _emit_progress(task_id, 25, "正在语音转写（ASR）...", "processing")
                segments: list[Segment] = self.transcriber.transcribe(audio_path)
                if not segments:
                    _emit_progress(task_id, 0, "语音转写失败", "failed")
                    return names, descs

                _emit_progress(task_id, 50, "LLM 分析事件结构...", "processing")
                events: list[EventItem] = self.extract_outline(
                    segments,
                    self.analyzer,
                    segment_duration_minutes=self.segment_duration_minutes,
                )
                if not events:
                    _save_result(task_id, [])
                    _emit_progress(task_id, 100, "未识别到精彩事件", "done")
                    return names, descs

                _emit_progress(task_id, 70, f"Omni 音频情绪筛选（共 {len(events)} 个事件）...", "processing")
                # final_events = sorted(self.refine_events_with_omni_v2(events), key=lambda x: x.start_time)

                self.final_events = events

                _emit_progress(task_id, 85, f"正在裁剪 {len(self.final_events)} 个精彩片段...", "processing")
                clips: list[dict[str, Any]] = []
                for idx, clip in enumerate(self.final_events, 1):
                    outname = f"clip_{current_video_path.stem}_{idx:02d}.mp4"
                    outpath = RESULT_DIR / outname
                    self.editor.crop_video(outpath, clip.start_time, clip.end_time)
                    names.append(str(outpath))
                    descs.append(clip.title)
                    clips.append(
                        {
                            "title": clip.title,
                            "description": clip.description,
                            "start_time": clip.start_time,
                            "end_time": clip.end_time,
                            "clip_file": outname,
                        }
                    )

                _save_result(task_id, clips)
                _emit_progress(task_id, 100, f"处理完成，共 {len(clips)} 个精彩片段", "done")
                return names, descs

        processor = ProgressProcessor(config)
        processor.process(video_path)

    except TaskCancelledError:
        _task_log(task_id, "INFO", "task cancelled manually")
        logger.info(f"task {task_id} cancelled manually")
    except Exception as exc:
        _task_log(task_id, "ERROR", f"task failed: {exc}")
        logger.exception(f"task {task_id} failed: {exc}")
        try:
            _emit_progress(task_id, 0, f"处理失败: {exc}", "failed")
        except TaskCancelledError:
            _task_log(task_id, "INFO", "task cancelled before failure reporting")
    finally:
        _ACTIVE_TASK_LOG_PATHS.pop(task_id, None)
        logger.remove(sink_id)


@celery_app.task(name="backend.process_video_task")
def process_video_task(task_id: int) -> None:
    _run_video_pipeline(task_id)
