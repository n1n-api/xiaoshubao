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

        # 仍然需要 history 目录来存储图片文件 (Vercel 环境下这依然是临时的)
        # 长期方案：图片应该上传到 S3 / R2 / OSS
        if os.environ.get('VERCEL'):
            self.history_dir = "/tmp/history"
        else:
            self.history_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "history"
            )
        os.makedirs(self.history_dir, exist_ok=True)

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
        扫描任务文件夹，同步图片列表到数据库
        注意：此功能依赖于文件系统中的图片文件。
        在 Serverless 环境中，如果图片丢失，此功能只能将数据库状态标记为失效或重置。
        """
        task_dir = os.path.join(self.history_dir, task_id)

        if not os.path.exists(task_dir) or not os.path.isdir(task_dir):
            return {
                "success": False,
                "error": f"任务目录不存在: {task_id}"
            }

        try:
            # 扫描目录下所有图片文件（排除缩略图）
            image_files = []
            for filename in os.listdir(task_dir):
                if filename.startswith('thumb_'):
                    continue
                if filename.endswith(('.png', '.jpg', '.jpeg')):
                    image_files.append(filename)

            # 按文件名排序
            def get_index(filename):
                try:
                    return int(filename.split('.')[0])
                except:
                    return 999
            image_files.sort(key=get_index)

            session = self.Session()
            try:
                # 查找关联的历史记录
                record = session.query(History).filter_by(task_id=task_id).first()
                
                if record:
                    # 更新逻辑
                    expected_count = len(record.outline.get("pages", [])) if record.outline else 0
                    actual_count = len(image_files)

                    status = record.status
                    if actual_count == 0:
                        status = "draft"
                    elif actual_count >= expected_count:
                        status = "completed"
                    else:
                        status = "partial"

                    # 更新数据库
                    current_images = record.images or {}
                    current_images["generated"] = image_files
                    current_images["task_id"] = task_id
                    
                    record.images = current_images
                    record.status = status
                    if image_files:
                        record.thumbnail = image_files[0]
                    
                    session.commit()

                    return {
                        "success": True,
                        "record_id": record.id,
                        "task_id": task_id,
                        "images_count": len(image_files),
                        "images": image_files,
                        "status": status
                    }
            finally:
                session.close()

            # 没有关联记录
            return {
                "success": True,
                "task_id": task_id,
                "images_count": len(image_files),
                "images": image_files,
                "no_record": True
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"扫描任务失败: {str(e)}"
            }

    def scan_all_tasks(self) -> Dict[str, Any]:
        """扫描所有任务文件夹"""
        if not os.path.exists(self.history_dir):
            return {"success": False, "error": "历史记录目录不存在"}

        try:
            results = []
            synced_count = 0
            failed_count = 0
            orphan_tasks = []

            for item in os.listdir(self.history_dir):
                item_path = os.path.join(self.history_dir, item)
                if not os.path.isdir(item_path):
                    continue

                task_id = item
                result = self.scan_and_sync_task_images(task_id)
                results.append(result)

                if result.get("success"):
                    if result.get("no_record"):
                        orphan_tasks.append(task_id)
                    else:
                        synced_count += 1
                else:
                    failed_count += 1

            return {
                "success": True,
                "total_tasks": len(results),
                "synced": synced_count,
                "failed": failed_count,
                "orphan_tasks": orphan_tasks,
                "results": results
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

_service_instance = None

def get_history_service() -> HistoryService:
    global _service_instance
    if _service_instance is None:
        _service_instance = HistoryService()
    return _service_instance
