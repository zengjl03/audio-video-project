import json
import threading
import time

import redis as redis_lib
from flask_socketio import SocketIO, emit, join_room

from ..config import REDIS_URL


def register_socket_events(socketio: SocketIO) -> None:
    @socketio.on("connect")
    def on_connect():
        emit("connected", {"msg": "connected"})

    @socketio.on("subscribe_task")
    def on_subscribe(data):
        task_id = data.get("task_id")
        if not task_id:
            return
        join_room(f"task_{task_id}")
        emit("subscribed", {"task_id": task_id})


def start_redis_listener(socketio: SocketIO) -> None:
    def run() -> None:
        while True:
            try:
                redis = redis_lib.from_url(
                    REDIS_URL,
                    decode_responses=True,
                    socket_keepalive=True,
                    socket_connect_timeout=5,
                )
                pubsub = redis.pubsub()
                pubsub.subscribe("task_progress")

                while True:
                    message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if not message or message.get("type") != "message":
                        time.sleep(0.1)
                        continue
                    try:
                        payload = json.loads(message["data"])
                        task_id = payload.get("task_id")
                        socketio.emit("task_progress", payload, room=f"task_{task_id}", namespace="/")
                        socketio.emit("task_update", payload, namespace="/")
                    except Exception:
                        pass
                    time.sleep(0.1)
            except Exception:
                time.sleep(3)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
