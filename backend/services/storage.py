import os
import logging
import boto3
from botocore.exceptions import ClientError
from backend.utils.config_manager import config_manager

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        # 尝试从环境变量或数据库配置加载 R2 配置
        self.config = self._load_config()
        self.s3_client = None
        
        if self._validate_config():
            try:
                self.s3_client = boto3.client(
                    's3',
                    endpoint_url=self.config['endpoint_url'],
                    aws_access_key_id=self.config['access_key_id'],
                    aws_secret_access_key=self.config['secret_access_key']
                )
                logger.info("✅ R2 存储服务初始化成功")
            except Exception as e:
                logger.error(f"❌ R2 存储服务初始化失败: {e}")

    def _load_config(self):
        # 优先从环境变量加载（Vercel 环境）
        config = {
            'endpoint_url': os.environ.get('R2_ENDPOINT_URL'),
            'access_key_id': os.environ.get('R2_ACCESS_KEY_ID'),
            'secret_access_key': os.environ.get('R2_SECRET_ACCESS_KEY'),
            'bucket_name': os.environ.get('R2_BUCKET_NAME'),
            'public_domain': os.environ.get('R2_PUBLIC_DOMAIN') # 可选：绑定的自定义域名
        }
        
        # 如果环境变量不全，尝试从数据库配置加载
        if not all([config['endpoint_url'], config['access_key_id'], config['secret_access_key']]):
            db_config = config_manager.get_config('storage_config') or {}
            if db_config:
                config.update(db_config)
                
        return config

    def _validate_config(self):
        required = ['endpoint_url', 'access_key_id', 'secret_access_key', 'bucket_name']
        return all(self.config.get(k) for k in required)

    def upload_file(self, file_data: bytes, object_name: str, content_type: str = 'image/png') -> str:
        """
        上传文件到 R2
        
        Args:
            file_data: 文件二进制数据
            object_name: 存储路径/文件名 (例如: task_123/image_1.png)
            content_type: 文件类型
            
        Returns:
            str: 文件的访问 URL
        """
        if not self.s3_client:
            logger.warning("R2 未配置，跳过上传")
            return ""

        try:
            self.s3_client.put_object(
                Bucket=self.config['bucket_name'],
                Key=object_name,
                Body=file_data,
                ContentType=content_type
            )
            
            # 生成访问 URL
            if self.config.get('public_domain'):
                # 如果配置了自定义域名
                domain = self.config['public_domain'].rstrip('/')
                return f"{domain}/{object_name}"
            else:
                # 否则使用预签名 URL (有效期 1 小时) 或 R2 默认域名
                # 这里为了简单，假设 R2 Bucket 开启了公共访问或有自定义域名
                # 如果是私有 Bucket，通常需要生成 Presigned URL
                # return self.s3_client.generate_presigned_url('get_object', Params={'Bucket': self.config['bucket_name'], 'Key': object_name}, ExpiresIn=3600)
                return f"{self.config['endpoint_url']}/{self.config['bucket_name']}/{object_name}"

        except ClientError as e:
            logger.error(f"上传文件失败: {e}")
            raise e

# 单例实例
storage_service = StorageService()

