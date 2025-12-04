import datetime
import json
from sqlalchemy import Column, String, Text, Integer, DateTime, JSON, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func

Base = declarative_base()

class History(Base):
    __tablename__ = 'history'

    id = Column(String(36), primary_key=True)  # UUID
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    outline = Column(JSON, nullable=False)  # 存储大纲 JSON
    images = Column(JSON, nullable=True)    # 存储图片信息的 JSON (task_id, generated list)
    status = Column(String(50), default='draft')
    thumbnail = Column(String(255), nullable=True)
    page_count = Column(Integer, default=0)
    task_id = Column(String(255), nullable=True) # 方便查询

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "outline": self.outline,
            "images": self.images or {"task_id": None, "generated": []},
            "status": self.status,
            "thumbnail": self.thumbnail,
            "page_count": self.page_count,
            "task_id": self.task_id
        }

# 数据库初始化逻辑
def init_db(db_url):
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)

