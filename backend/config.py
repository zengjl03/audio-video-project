import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent  # 项目根目录

# 上传/结果目录
UPLOAD_DIR = BASE_DIR / "backend" / "uploads"
RESULT_DIR = BASE_DIR / "backend" / "results"
LOG_DIR = BASE_DIR / "backend" / "logs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 数据库
DB_PATH = BASE_DIR / "backend" / "audio_video.db"

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://:abc123@127.0.0.1:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TASK_QUEUE = os.getenv("CELERY_TASK_QUEUE", "video_processing")

# Flask
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod")

# Agent 配置（从 .env 读取，与 main_v2.py 保持一致）
BASE_URL = os.getenv("BASE_URL", "")
API_KEY = os.getenv("API_KEY", "")
OUTLINE_MODEL = os.getenv("OUTLINE_MODEL", "gpt-4.1")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", str(RESULT_DIR))

# 视频分块时长（分钟）
SEGMENT_DURATION_MINUTES = int(os.getenv("SEGMENT_DURATION_MINUTES", "30"))

# 断点续传分块大小（字节，1MB）
CHUNK_SIZE = 1 * 1024 * 1024

# 默认 Prompt 内容（育儿建议方向）
DEFAULT_PROMPT = """## 核心任务：精准识别有趣、家庭欢笑、开心的环节并返回时间戳

你是一位专业的家庭生活场景内容结构分析师，你的任务是**从转录文本片段中精准识别出有趣、家庭欢笑、开心的环节**，基于这些有趣片段点适当扩展（包含前因后果），返回每个完整开心事件的完整时间戳。

### 核心目标：
- **精准识别**：只识别真正有趣、家庭欢笑、开心的环节，不要包含普通对话或日常交流
- **适当扩展**：以有趣片段为核心，向前向后扩展必要的上下文，让人能够理解这个开心事件的前因后果
- **完整性**：每个开心事件应该包含完整的开心场景，从引发开心的原因到开心的表达

### 开心事件的特征：
- **情绪明显**：包含明显的笑声、开心的表达、兴奋的语气（如"哈哈"、"太好了"、"太棒了"等）
- **家庭互动**：体现家庭成员之间的欢乐互动、温馨时刻
- **有趣内容**：包含有趣的话题、搞笑的对话、惊喜的发现等
- **语义完整**：从引发开心的原因到开心的表达，形成一个完整的开心场景
"""
