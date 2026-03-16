import json
import shutil
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

import redis as redis_lib
from flask import Flask, jsonify, request, send_from_directory

from ..config import DEFAULT_PROMPT, LOG_DIR, REDIS_URL, RESULT_DIR, UPLOAD_DIR
from .celery_app import celery_app
from .models import Prompt, Task, db, set_current_prompt
from .tasks import process_video_task


@contextmanager
def db_connection():
    db.connect(reuse_if_open=True)
    try:
        yield
    finally:
        if not db.is_closed():
            db.close()


_redis_client = redis_lib.from_url(REDIS_URL, decode_responses=True)


def _parse_result(value: str | None):
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


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


def _task_to_response(task: Task) -> dict:
    return {
        "id": task.id,
        "task_id": task.task_id,
        "filename": task.filename,
        "status": task.status,
        "progress": task.progress,
        "progress_msg": task.progress_msg,
        "result": _parse_result(task.result_json),
        "upload_file": Path(task.file_path).name if task.file_path else None,
        "log_file": _task_log_path(task.id).name if _task_log_path(task.id).exists() else None,
        "created_at": task.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": task.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _publish_task_update(task: Task, msg: str) -> None:
    payload = json.dumps(
        {
            "task_id": task.id,
            "progress": task.progress,
            "msg": msg,
            "status": task.status,
        },
        ensure_ascii=False,
    )
    _redis_client.publish("task_progress", payload)


def _build_stats_payload(tasks: list[Task]) -> dict:
    total = len(tasks)
    done = sum(1 for t in tasks if t.status == "done")
    failed = sum(1 for t in tasks if t.status == "failed")
    processing = sum(1 for t in tasks if t.status == "processing")
    uploaded = sum(1 for t in tasks if t.status == "uploaded")

    durations = [
        max(0.0, (t.updated_at - t.created_at).total_seconds())
        for t in tasks
        if t.status in {"done", "failed"}
    ]
    avg_duration = sum(durations) / len(durations) if durations else 0.0

    today = date.today()
    start = today - timedelta(days=13)
    by_day: dict[str, dict[str, int]] = defaultdict(lambda: {"done": 0, "failed": 0})
    for t in tasks:
        day = t.created_at.date()
        if day < start:
            continue
        key = day.strftime("%m-%d")
        if t.status == "done":
            by_day[key]["done"] += 1
        elif t.status == "failed":
            by_day[key]["failed"] += 1

    trend = []
    for i in range(14):
        d = start + timedelta(days=i)
        key = d.strftime("%m-%d")
        trend.append({"date": key, "done": by_day[key]["done"], "failed": by_day[key]["failed"]})

    return {
        "total_tasks": total,
        "done_tasks": done,
        "failed_tasks": failed,
        "processing_tasks": processing,
        "uploaded_tasks": uploaded,
        "success_rate": round((done / total * 100.0), 2) if total else 0.0,
        "avg_processing_seconds": round(avg_duration, 2),
        "trend_14d": trend,
    }


def register_routes(app: Flask, project_root: Path) -> None:
    def get_chunk_path(identifier: str, chunk_number: int) -> Path:
        chunk_dir = UPLOAD_DIR / "chunks" / identifier
        chunk_dir.mkdir(parents=True, exist_ok=True)
        return chunk_dir / f"chunk_{chunk_number:05d}"

    def assemble_chunks(identifier: str, total_chunks: int, filename: str) -> Path:
        final_path = UPLOAD_DIR / f"{identifier}_{filename}"
        with open(final_path, "wb") as f_out:
            for idx in range(1, total_chunks + 1):
                chunk_path = get_chunk_path(identifier, idx)
                with open(chunk_path, "rb") as f_in:
                    f_out.write(f_in.read())
        shutil.rmtree(UPLOAD_DIR / "chunks" / identifier, ignore_errors=True)
        return final_path

    @app.route("/api/upload/check", methods=["GET"])
    def upload_check():
        identifier = request.args.get("resumableIdentifier", "")
        chunk_number = int(request.args.get("resumableChunkNumber", 0))
        if get_chunk_path(identifier, chunk_number).exists():
            return jsonify({"status": "found"}), 200
        return jsonify({"status": "not_found"}), 204

    @app.route("/api/upload/chunk", methods=["POST"])
    def upload_chunk():
        identifier = request.form.get("resumableIdentifier", "")
        chunk_number = int(request.form.get("resumableChunkNumber", 0))
        total_chunks = int(request.form.get("resumableTotalChunks", 1))
        filename = request.form.get("resumableFilename", "video.mp4")

        file = request.files.get("file")
        if not file:
            return jsonify({"error": "no file"}), 400

        file.save(str(get_chunk_path(identifier, chunk_number)))
        chunk_dir = UPLOAD_DIR / "chunks" / identifier
        uploaded = len(list(chunk_dir.glob("chunk_*")))
        if uploaded < total_chunks:
            return jsonify({"status": "partial", "uploaded": uploaded, "total": total_chunks}), 200

        final_path = assemble_chunks(identifier, total_chunks, filename)
        with db_connection():
            task = Task.create(
                filename=filename,
                file_path=str(final_path),
                status="uploaded",
                progress=0,
                progress_msg="文件已上传，等待处理",
            )
        return jsonify({"status": "complete", "task_id": task.id}), 200

    @app.route("/api/tasks", methods=["GET"])
    def list_tasks():
        with db_connection():
            tasks = list(Task.select().order_by(Task.created_at.desc()).limit(100))
            return jsonify([_task_to_response(t) for t in tasks])

    @app.route("/api/demo-samples", methods=["GET"])
    def demo_samples():
        with db_connection():
            samples = (
                Task.select()
                .where(Task.status == "done")
                .order_by(Task.updated_at.desc())
                .limit(12)
            )
            payload = []
            for task in samples:
                data = _task_to_response(task)
                clips = data.get("result") or []
                data["clip_count"] = len(clips)
                data["has_preview"] = bool(data.get("upload_file"))
                payload.append(data)
            return jsonify(payload)

    @app.route("/api/tasks/<int:task_id>", methods=["GET"])
    def get_task(task_id: int):
        with db_connection():
            task = Task.get_or_none(Task.id == task_id)
            if not task:
                return jsonify({"error": "not found"}), 404
            return jsonify(_task_to_response(task))

    @app.route("/api/tasks/<int:task_id>/start", methods=["POST"])
    def start_task(task_id: int):
        with db_connection():
            task = Task.get_or_none(Task.id == task_id)
            if not task:
                return jsonify({"error": "not found"}), 404
            if task.status == "processing":
                return jsonify({"error": "already processing"}), 400
            if task.status not in {"uploaded", "failed"}:
                return jsonify({"error": f"cannot start from status={task.status}"}), 400

            try:
                async_result = process_video_task.delay(task_id)
            except Exception as exc:
                return jsonify({"error": f"queue unavailable: {exc}"}), 503

            task.task_id = async_result.id
            task.status = "processing"
            task.progress = 0
            task.progress_msg = "任务已提交，等待 Worker 执行..."
            task.save()
            _publish_task_update(task, task.progress_msg)
            return jsonify({"status": "ok", "job_id": async_result.id})

    @app.route("/api/tasks/<int:task_id>/stop", methods=["POST"])
    def stop_task(task_id: int):
        with db_connection():
            task = Task.get_or_none(Task.id == task_id)
            if not task:
                return jsonify({"error": "not found"}), 404
            if task.status != "processing":
                return jsonify({"error": "task is not processing"}), 400

            if task.task_id:
                celery_app.control.revoke(task.task_id, terminate=True)

            task.status = "failed"
            task.progress_msg = "任务已手动终止，可重新发起"
            task.save()
            _publish_task_update(task, task.progress_msg)
            return jsonify({"status": "stopped"})

    @app.route("/api/tasks/<int:task_id>/logs", methods=["GET"])
    def task_logs(task_id: int):
        tail = int(request.args.get("tail", 300))
        log_path = _task_log_path(task_id)
        if not log_path.exists():
            return jsonify({"lines": [], "exists": False})
        lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return jsonify({"exists": True, "lines": lines[-tail:]})

    @app.route("/api/tasks/<int:task_id>/logs/raw", methods=["GET"])
    def task_logs_raw(task_id: int):
        log_path = _task_log_path(task_id)
        if not log_path.exists():
            return jsonify({"error": "log not found"}), 404
        return send_from_directory(str(LOG_DIR), log_path.name, as_attachment=True)

    @app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
    def delete_task(task_id: int):
        with db_connection():
            task = Task.get_or_none(Task.id == task_id)
            if not task:
                return jsonify({"error": "not found"}), 404
            task.delete_instance()
            for path in LOG_DIR.glob(f"{_task_log_prefix(task_id)}*.log"):
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass
            legacy_log = LOG_DIR / f"task_{task_id}.log"
            try:
                legacy_log.unlink(missing_ok=True)
            except Exception:
                pass
            return jsonify({"status": "deleted"})

    @app.route("/api/prompt", methods=["GET"])
    def get_prompt():
        with db_connection():
            prompt = Prompt.select().order_by(Prompt.id.desc()).first()
            if prompt:
                return jsonify(
                    {
                        "content": prompt.content,
                        "updated_at": prompt.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
            return jsonify({"content": DEFAULT_PROMPT, "updated_at": None})

    @app.route("/api/prompt", methods=["POST"])
    def update_prompt():
        data = request.get_json(silent=True) or {}
        content = data.get("content", "").strip()
        if not content:
            return jsonify({"error": "content 不能为空"}), 400

        prompt = set_current_prompt(content)
        return jsonify({"status": "ok", "updated_at": prompt.updated_at.strftime("%Y-%m-%d %H:%M:%S")})

    @app.route("/api/stats", methods=["GET"])
    def stats():
        with db_connection():
            tasks = list(Task.select().order_by(Task.created_at.desc()).limit(1000))
        return jsonify(_build_stats_payload(tasks))

    @app.route("/api/results/<path:filename>")
    def serve_result(filename: str):
        return send_from_directory(str(RESULT_DIR), filename)

    @app.route("/api/uploads/<path:filename>")
    def serve_upload(filename: str):
        return send_from_directory(str(UPLOAD_DIR), filename)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path: str):
        dist_dir = project_root / "frontend" / "dist"
        if path and (dist_dir / path).exists():
            return send_from_directory(str(dist_dir), path)
        if (dist_dir / "index.html").exists():
            return send_from_directory(str(dist_dir), "index.html")
        return jsonify({"msg": "Frontend not built. Run: cd frontend && npm run build"}), 200
