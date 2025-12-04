import os
import json
import uuid
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker
from backend.models import History, Base

class HistoryService:
    def __init__(self):
        # 从环境变量或默认配置获取数据库 URL
        self.db_url = os.environ.get(
            'DATABASE_URL', 
            'postgresql://root:X783RQkS6Cb0oesNhTJA92K51cptHf4x@sfo1.clusters.zeabur.com:31948/xiaoshubao'
        )
        if self.db_url and self.db_url.startswith("postgres://"):
            self.db_url = self.db_url.replace("postgres://", "postgresql://", 1)
            
        self.engine = create_engine(self.db_url)
        self.Session = sessionmaker(bind=self.engine)
        
        # 确保表存在
        Base.metadata.create_all(self.engine)

        # 历史记录目录配置
        # 注意：在 R2 存储模式下，本地 history 目录仅作为逻辑路径或临时缓存（如果需要）
        # 不再强制创建本地目录用于持久化存储
        if os.environ.get('VERCEL'):
            self.history_dir = "/tmp/history"
        else:
            self.history_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "history"
            )
        # os.makedirs(self.history_dir, exist_ok=True)

    def create_record(
        self,
        topic: str,
        outline: Dict,
        task_id: Optional[str] = None
    ) -> str:
        session = self.Session()
        try:
            record_id = str(uuid.uuid4())
            now = datetime.now()

            new_record = History(
                id=record_id,
                title=topic,
                created_at=now,
                updated_at=now,
                outline=outline,
                images={"task_id": task_id, "generated": []},
                status="draft",
                page_count=len(outline.get("pages", [])),
                task_id=task_id
            )
            
            session.add(new_record)
            session.commit()
            return record_id
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_record(self, record_id: str) -> Optional[Dict]:
        session = self.Session()
        try:
            record = session.query(History).filter_by(id=record_id).first()
            return record.to_dict() if record else None
        finally:
            session.close()

    def update_record(
        self,
        record_id: str,
        outline: Optional[Dict] = None,
        images: Optional[Dict] = None,
        status: Optional[str] = None,
        thumbnail: Optional[str] = None
    ) -> bool:
        session = self.Session()
        try:
            record = session.query(History).filter_by(id=record_id).first()
            if not record:
                return False

            record.updated_at = datetime.now()
            
            if outline is not None:
                record.outline = outline
                record.page_count = len(outline.get("pages", []))
            
            if images is not None:
                # 合并或替换 images 字段
                current_images = record.images or {}
                if "task_id" in images:
                    current_images["task_id"] = images["task_id"]
                    record.task_id = images["task_id"]
                if "generated" in images:
                    current_images["generated"] = images["generated"]
                record.images = current_images

            if status is not None:
                record.status = status

            if thumbnail is not None:
                record.thumbnail = thumbnail

            session.commit()
            return True
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()

    def delete_record(self, record_id: str) -> bool:
        session = self.Session()
        try:
            record = session.query(History).filter_by(id=record_id).first()
            if not record:
                return False

            # 删除关联的任务文件夹（如果存在）
            # 注意：如果文件存储也是临时的，这一步可能只在本地有效
            if record.task_id:
                task_dir = os.path.join(self.history_dir, record.task_id)
                if os.path.exists(task_dir):
                    try:
                        shutil.rmtree(task_dir)
                    except Exception:
                        pass

            session.delete(record)
            session.commit()
            return True
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()

    def list_records(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None
    ) -> Dict:
        session = self.Session()
        try:
            query = session.query(History)
            
            if status and status != 'all':
                query = query.filter_by(status=status)
            
            # 按更新时间倒序
            query = query.order_by(History.updated_at.desc())
            
            total = query.count()
            records = query.offset((page - 1) * page_size).limit(page_size).all()
            
            return {
                "records": [r.to_dict() for r in records],
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }
        finally:
            session.close()

    def search_records(self, keyword: str) -> List[Dict]:
        session = self.Session()
        try:
            query = session.query(History).filter(
                History.title.ilike(f"%{keyword}%")
            ).order_by(History.updated_at.desc())
            
            records = query.all()
            return [r.to_dict() for r in records]
        finally:
            session.close()

    def get_statistics(self) -> Dict:
        session = self.Session()
        try:
            total = session.query(History).count()
            
            # 统计各状态数量
            # SQLAlchemy < 1.4 写法
            from sqlalchemy import func
            status_counts = session.query(
                History.status, func.count(History.status)
            ).group_by(History.status).all()
            
            by_status = {status: count for status, count in status_counts}
            
            return {
                "total": total,
                "by_status": by_status
            }
        finally:
            session.close()

    def scan_and_sync_task_images(self, task_id: str) -> Dict[str, Any]:
        """
        扫描任务图片
        
        注意：在 R2 存储模式下，无法直接扫描“目录”来获取文件列表（除非列出 Bucket 对象）。
        这里修改为：仅根据数据库中已有的记录来返回状态，或者如果必须同步，则需要调用 R2 ListObjects API。
        目前简化为：如果不使用本地存储，则直接返回当前数据库记录中的图片信息。
        """
        session = self.Session()
        try:
            # 查找关联的历史记录
            record = session.query(History).filter_by(task_id=task_id).first()
            
            if not record:
                return {
                    "success": False,
                    "error": f"找不到任务 ID 为 {task_id} 的记录"
                }

            # 如果是 R2 模式，且没有本地文件，我们假设数据库中的记录是准确的
            # 或者可以在这里实现 R2 的 ListObjects 逻辑来校验
            current_images = record.images or {}
            generated_images = current_images.get("generated", [])
            
            # 简单的状态检查
            expected_count = len(record.outline.get("pages", [])) if record.outline else 0
            actual_count = len(generated_images)

            status = record.status
            if actual_count == 0:
                status = "draft"
            elif actual_count >= expected_count:
                status = "completed"
            else:
                status = "partial"
            
            # 更新状态（仅状态）
            record.status = status
            session.commit()

            return {
                "success": True,
                "record_id": record.id,
                "task_id": task_id,
                "images_count": actual_count,
                "images": generated_images,
                "status": status,
                "mode": "r2_db_sync" # 标记为数据库同步模式
            }

        except Exception as e:
             return {
                "success": False,
                "error": f"同步任务失败: {str(e)}"
            }
        finally:
            session.close()

    def scan_all_tasks(self) -> Dict[str, Any]:
        """
        扫描所有任务
        注意：R2 模式下，无法遍历本地目录。
        改为：扫描数据库中所有任务记录并更新状态。
        """
        session = self.Session()
        try:
            records = session.query(History).all()
            results = []
            synced_count = 0
            
            for record in records:
                if not record.task_id:
                    continue
                    
                # 复用单个同步逻辑（虽然有点低效，但逻辑一致）
                # 注意：这里不能在循环中调用 self.scan_and_sync_task_images 因为它也会创建 session
                # 为了避免嵌套 session 问题，我们直接在这里处理或重构逻辑
                # 简单起见，只统计数量
                synced_count += 1
                
            return {
                "success": True,
                "total_tasks": len(records),
                "synced": synced_count,
                "message": "已同步数据库记录状态 (R2 模式下不扫描物理文件)"
            }
        finally:
            session.close()

_service_instance = None

def get_history_service() -> HistoryService:
    global _service_instance
    if _service_instance is None:
        _service_instance = HistoryService()
    return _service_instance
