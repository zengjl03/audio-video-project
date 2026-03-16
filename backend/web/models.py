import datetime
from peewee import (
    SqliteDatabase,
    Model,
    AutoField,
    CharField,
    TextField,
    DateTimeField,
    IntegerField,
)

from playhouse.shortcuts import model_to_dict
from ..config import DB_PATH, DEFAULT_PROMPT

db = SqliteDatabase(str(DB_PATH))


class BaseModel(Model):
    class Meta:
        database = db

    def to_dict(self, exclude_fields=None):
        """
        将模型实例转为字典
        :param exclude_fields: 要排除的字段列表（如敏感字段）
        :return: 字典格式的模型数据
        """
        # 默认排除的字段（可根据业务调整）
        exclude = exclude_fields or []
        # 使用官方工具函数转换，自动处理字段类型（如 datetime 转字符串）
        return model_to_dict(
            self,
            exclude=exclude,
            # 可选：是否递归转换关联模型（如外键字段）
            recurse=False
        )


class Task(BaseModel):
    """视频处理任务"""
    id = AutoField()
    task_id = CharField(max_length=64, null=True)
    filename = CharField(max_length=255)
    file_path = CharField(max_length=512)
    status = CharField(
        max_length=20,
        default="pending",
        # pending / uploading / processing / done / failed
    )
    progress = IntegerField(default=0)          # 0-100
    progress_msg = TextField(default="")        # 当前阶段描述
    result_json = TextField(null=True)          # JSON 字符串，存储 events 列表
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.now()
        return super().save(*args, **kwargs)

    class Meta:
        table_name = "tasks"


class Prompt(BaseModel):
    """全局 Prompt（单行记录）"""
    id = AutoField()
    content = TextField()
    updated_at = DateTimeField(default=datetime.datetime.now)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.now()
        return super().save(*args, **kwargs)

    class Meta:
        table_name = "prompts"


def init_db():
    """初始化数据库，创建表并插入默认数据"""
    db.connect(reuse_if_open=True)
    db.create_tables([Task, Prompt], safe=True)

    # 若 Prompt 表为空，插入默认 Prompt
    if Prompt.select().count() == 0:
        Prompt.create(content=DEFAULT_PROMPT)

    db.close()


def get_current_prompt() -> str:
    """获取当前全局 Prompt 内容"""
    db.connect(reuse_if_open=True)
    try:
        p = Prompt.select().order_by(Prompt.id.desc()).first()
        return p.content if p else DEFAULT_PROMPT
    finally:
        db.close()


def set_current_prompt(content: str) -> Prompt:
    """更新全局 Prompt，返回更新后的对象"""
    db.connect(reuse_if_open=True)
    try:
        p = Prompt.select().order_by(Prompt.id.desc()).first()
        if p:
            p.content = content
            p.save()
        else:
            p = Prompt.create(content=content)
        return p
    finally:
        db.close()
