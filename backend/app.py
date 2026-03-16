import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask_socketio import SocketIO

from .config import REDIS_URL, SECRET_KEY
from .web.models import init_db
from .web.realtime import register_socket_events, start_redis_listener
from .web.routes import register_routes

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def create_app() -> tuple[Flask, SocketIO]:
    app = Flask(
        __name__,
        static_folder=str(PROJECT_ROOT / "frontend" / "dist"),
        static_url_path="",
    )
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024 * 1024

    async_mode = os.getenv("SOCKETIO_ASYNC_MODE", "threading")
    socketio = SocketIO(
        app,
        async_mode=async_mode,
        message_queue=REDIS_URL,
        cors_allowed_origins="*",
        logger=False,
        engineio_logger=False,
    )

    init_db()
    register_routes(app, PROJECT_ROOT)
    register_socket_events(socketio)
    return app, socketio


app, socketio = create_app()


if __name__ == "__main__":
    start_redis_listener(socketio)
    port = int(os.getenv("PORT", 5000))
    print(f"Flask server started: http://localhost:{port}")
    socketio.run(app, host="127.0.0.1", port=port, debug=False)
