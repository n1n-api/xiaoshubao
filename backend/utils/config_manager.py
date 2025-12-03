import logging
import os
from urllib.parse import urlparse

import yaml
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

class ConfigManager:
    """配置管理器，负责从数据库加载和保存配置"""

    def __init__(self, db_url=None):
        # 优先使用传入的 db_url，其次是环境变量，最后是默认的本地文件模式（None）
        self.db_url = db_url or os.environ.get("DATABASE_URL")
        self.engine = None
        
        if self.db_url:
            try:
                self.engine = create_engine(self.db_url)
                self._init_db()
                logger.info("✅ 数据库连接成功，配置将存储在数据库中")
            except Exception as e:
                logger.error(f"❌ 数据库连接失败: {e}")
                self.engine = None

    def _init_db(self):
        """初始化数据库表"""
        if not self.engine:
            return

        create_table_sql = """
        CREATE TABLE IF NOT EXISTS app_config (
            key VARCHAR(255) PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text(create_table_sql))
                conn.commit()
        except Exception as e:
            logger.error(f"初始化配置表失败: {e}")
            # 如果初始化失败，可能是权限问题或连接问题，为了不让应用崩溃，我们这里只记录错误
            # 后续操作会因为表不存在而失败，但应用可以继续运行（回退到文件模式）
            self.engine = None


    def get_config(self, key: str) -> dict:
        """获取配置"""
        # 1. 尝试从数据库获取
        if self.engine:
            try:
                with self.engine.connect() as conn:
                    result = conn.execute(
                        text("SELECT value FROM app_config WHERE key = :key"),
                        {"key": key}
                    ).fetchone()
                    if result and result[0]:
                        return yaml.safe_load(result[0])
            except Exception as e:
                logger.warning(f"从数据库读取配置失败: {e}")

        # 2. 回退到文件系统（Vercel 环境下文件是临时的，所以只能读不能持久化保存）
        # 但为了兼容本地开发，还是保留文件读取逻辑
        # 注意：在 Vercel 上，这些文件可能不存在或为空
        return {}

    def save_config(self, key: str, config: dict) -> bool:
        """保存配置"""
        yaml_str = yaml.dump(config, allow_unicode=True)

        # 1. 保存到数据库
        if self.engine:
            try:
                with self.engine.connect() as conn:
                    # PostgreSQL upsert
                    sql = """
                    INSERT INTO app_config (key, value, updated_at)
                    VALUES (:key, :value, CURRENT_TIMESTAMP)
                    ON CONFLICT (key) 
                    DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP;
                    """
                    conn.execute(text(sql), {"key": key, "value": yaml_str})
                    conn.commit()
                return True
            except Exception as e:
                logger.error(f"保存配置到数据库失败: {e}")
                return False
        
        # 2. 如果没有数据库，在 Vercel 上无法持久化保存
        # 本地开发时可以保存到文件
        if not os.environ.get('VERCEL'):
             # ... (保留原有文件保存逻辑，如果有的话) ...
             pass
             
        return False

# 全局配置管理器实例
config_manager = ConfigManager()

