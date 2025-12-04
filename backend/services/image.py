"""图片生成服务"""
import logging
import os
import uuid
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Generator, List, Optional, Tuple
from backend.config import Config
from backend.generators.factory import ImageGeneratorFactory
from backend.utils.image_compressor import compress_image

logger = logging.getLogger(__name__)


class ImageService:
    """图片生成服务类"""

    # 并发配置
    MAX_CONCURRENT = 15  # 最大并发数
    AUTO_RETRY_COUNT = 3  # 自动重试次数

    def __init__(self, provider_name: str = None):
        """
        初始化图片生成服务

        Args:
            provider_name: 服务商名称，如果为None则使用配置文件中的激活服务商
        """
        logger.debug("初始化 ImageService...")

        # 获取服务商配置
        if provider_name is None:
            provider_name = Config.get_active_image_provider()

        logger.info(f"使用图片服务商: {provider_name}")
        provider_config = Config.get_image_provider_config(provider_name)

        # 创建生成器实例
        provider_type = provider_config.get('type', provider_name)
        logger.debug(f"创建生成器: type={provider_type}")
        self.generator = ImageGeneratorFactory.create(provider_type, provider_config)

        # 保存配置信息
        self.provider_name = provider_name
        self.provider_config = provider_config

        # 检查是否启用短 prompt 模式
        self.use_short_prompt = provider_config.get('short_prompt', False)

        # 加载提示词模板
        self.prompt_template = self._load_prompt_template()
        self.prompt_template_short = self._load_prompt_template(short=True)

        # 历史记录根目录 (不再创建本地目录，仅保留路径结构用于逻辑兼容)
        if os.environ.get('VERCEL'):
            self.history_root_dir = "/tmp/history"
        else:
            self.history_root_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "history"
            )
        # 移除本地目录创建
        # os.makedirs(self.history_root_dir, exist_ok=True)

        # 当前任务的输出目录（仅作为逻辑路径）
        self.current_task_dir = None

        # 存储任务状态（用于重试）
        self._task_states: Dict[str, Dict] = {}

        logger.info(f"ImageService 初始化完成: provider={provider_name}, type={provider_type}")

    def _load_prompt_template(self, short: bool = False) -> str:
        """加载 Prompt 模板"""
        filename = "image_prompt_short.txt" if short else "image_prompt.txt"
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "prompts",
            filename
        )
        if not os.path.exists(prompt_path):
            # 如果短模板不存在，返回空字符串
            return ""
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    def _save_image(self, image_data: bytes, filename: str, task_id_or_path: str = None) -> str:
        """
        直接上传图片到 R2
        """
        from backend.services.storage import storage_service

        if task_id_or_path is None:
            task_id_or_path = self.current_task_dir

        if task_id_or_path is None:
            raise ValueError("任务ID未设置")

        # 获取 task_id (从路径中提取或直接使用)
        task_id = os.path.basename(task_id_or_path)
        object_name = f"{task_id}/{filename}"
        
        try:
            # 上传原图
            storage_service.upload_file(image_data, object_name, 'image/png')
            
            # 生成并上传缩略图
            thumbnail_data = compress_image(image_data, max_size_kb=50)
            thumbnail_filename = f"thumb_{filename}"
            thumb_object_name = f"{task_id}/{thumbnail_filename}"
            
            storage_service.upload_file(thumbnail_data, thumb_object_name, 'image/jpeg')
            
            logger.info(f"图片已上传到 R2: {object_name}")
            return object_name # 返回对象键名
            
        except Exception as e:
            logger.error(f"上传图片到 R2 失败: {e}")
            raise Exception(f"图片上传失败: {str(e)}。请检查 R2 配置。")

    def _generate_single_image(
        self,
        page: Dict,
        task_id: str,
        reference_image: Optional[bytes] = None,
        retry_count: int = 0,
        full_outline: str = "",
        user_images: Optional[List[bytes]] = None,
        user_topic: str = ""
    ) -> Tuple[int, bool, Optional[str], Optional[str], Optional[bytes]]:
        """
        生成单张图片（带自动重试）

        Returns:
            (index, success, filename, error_message, image_data)
        """
        index = page["index"]
        page_type = page["type"]
        page_content = page["content"]

        max_retries = self.AUTO_RETRY_COUNT

        for attempt in range(max_retries):
            try:
                logger.debug(f"生成图片 [{index}]: type={page_type}, attempt={attempt + 1}/{max_retries}")

                # 根据配置选择模板（短 prompt 或完整 prompt）
                if self.use_short_prompt and self.prompt_template_short:
                    # 短 prompt 模式：只包含页面类型和内容
                    prompt = self.prompt_template_short.format(
                        page_content=page_content,
                        page_type=page_type
                    )
                    logger.debug(f"  使用短 prompt 模式 ({len(prompt)} 字符)")
                else:
                    # 完整 prompt 模式：包含大纲和用户需求
                    prompt = self.prompt_template.format(
                        page_content=page_content,
                        page_type=page_type,
                        full_outline=full_outline,
                        user_topic=user_topic if user_topic else "未提供"
                    )

                # 调用生成器生成图片
                image_data = None
                if self.provider_config.get('type') == 'google_genai':
                    logger.debug(f"  使用 Google GenAI 生成器")
                    image_data = self.generator.generate_image(
                        prompt=prompt,
                        aspect_ratio=self.provider_config.get('default_aspect_ratio', '3:4'),
                        temperature=self.provider_config.get('temperature', 1.0),
                        model=self.provider_config.get('model', 'gemini-3-pro-image-preview'),
                        reference_image=reference_image,
                    )
                elif self.provider_config.get('type') == 'image_api':
                    logger.debug(f"  使用 Image API 生成器")
                    # Image API 支持多张参考图片
                    reference_images = []
                    if user_images:
                        reference_images.extend(user_images)
                    if reference_image:
                        reference_images.append(reference_image)

                    image_data = self.generator.generate_image(
                        prompt=prompt,
                        aspect_ratio=self.provider_config.get('default_aspect_ratio', '3:4'),
                        temperature=self.provider_config.get('temperature', 1.0),
                        model=self.provider_config.get('model', 'nano-banana-2'),
                        reference_images=reference_images if reference_images else None,
                    )
                else:
                    logger.debug(f"  使用 OpenAI 兼容生成器")
                    image_data = self.generator.generate_image(
                        prompt=prompt,
                        size=self.provider_config.get('default_size', '1024x1024'),
                        model=self.provider_config.get('model'),
                        quality=self.provider_config.get('quality', 'standard'),
                    )

                if not image_data:
                    raise Exception("生成器返回空数据")

                # 上传到 R2
                filename = f"{index}.png"
                self._save_image(image_data, filename, task_id)
                logger.info(f"✅ 图片 [{index}] 生成成功: {filename}")

                return (index, True, filename, None, image_data)

            except Exception as e:
                error_msg = str(e)
                logger.warning(f"图片 [{index}] 生成失败 (尝试 {attempt + 1}/{max_retries}): {error_msg[:200]}")

                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.debug(f"  等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue

                logger.error(f"❌ 图片 [{index}] 生成失败，已达最大重试次数")
                return (index, False, None, error_msg, None)

        return (index, False, None, "超过最大重试次数", None)

    def generate_images(
        self,
        pages: list,
        task_id: str = None,
        full_outline: str = "",
        user_images: Optional[List[bytes]] = None,
        user_topic: str = ""
    ) -> Generator[Dict[str, Any], None, None]:
        """
        生成图片（生成器，支持 SSE 流式返回）
        """
        if task_id is None:
            task_id = f"task_{uuid.uuid4().hex[:8]}"

        logger.info(f"开始图片生成任务: task_id={task_id}, pages={len(pages)}")

        # 设置任务目录路径（仅作为逻辑标识，不创建目录）
        self.current_task_dir = os.path.join(self.history_root_dir, task_id)
        logger.debug(f"任务逻辑路径: {self.current_task_dir}")

        total = len(pages)
        generated_images = []
        failed_pages = []
        cover_image_data = None

        # 压缩用户上传的参考图到200KB以内
        compressed_user_images = None
        if user_images:
            compressed_user_images = [compress_image(img, max_size_kb=200) for img in user_images]

        # 初始化任务状态
        self._task_states[task_id] = {
            "pages": pages,
            "generated": {},
            "failed": {},
            "cover_image": None,
            "full_outline": full_outline,
            "user_images": compressed_user_images,
            "user_topic": user_topic
        }

        # ==================== 第一阶段：生成封面 ====================
        cover_page = None
        other_pages = []

        for page in pages:
            if page["type"] == "cover":
                cover_page = page
            else:
                other_pages.append(page)

        if cover_page is None and len(pages) > 0:
            cover_page = pages[0]
            other_pages = pages[1:]

        if cover_page:
            yield {
                "event": "progress",
                "data": {
                    "index": cover_page["index"],
                    "status": "generating",
                    "message": "正在生成封面...",
                    "current": 1,
                    "total": total,
                    "phase": "cover"
                }
            }

            index, success, filename, error, image_data = self._generate_single_image(
                cover_page, task_id, reference_image=None, full_outline=full_outline,
                user_images=compressed_user_images, user_topic=user_topic
            )

            if success and image_data:
                generated_images.append(filename)
                self._task_states[task_id]["generated"][index] = filename

                # 直接使用内存中的图片数据
                cover_image_data = compress_image(image_data, max_size_kb=200)
                self._task_states[task_id]["cover_image"] = cover_image_data

                yield {
                    "event": "complete",
                    "data": {
                        "index": index,
                        "status": "done",
                        "image_url": f"/api/images/{task_id}/{filename}",
                        "phase": "cover"
                    }
                }
            else:
                failed_pages.append(cover_page)
                self._task_states[task_id]["failed"][index] = error or "Unknown error"

                yield {
                    "event": "error",
                    "data": {
                        "index": index,
                        "status": "error",
                        "message": error,
                        "retryable": True,
                        "phase": "cover"
                    }
                }

        # ==================== 第二阶段：生成其他页面 ====================
        if other_pages:
            high_concurrency = self.provider_config.get('high_concurrency', False)

            if high_concurrency:
                yield {
                    "event": "progress",
                    "data": {
                        "status": "batch_start",
                        "message": f"开始并发生成 {len(other_pages)} 页内容...",
                        "current": len(generated_images),
                        "total": total,
                        "phase": "content"
                    }
                }

                with ThreadPoolExecutor(max_workers=self.MAX_CONCURRENT) as executor:
                    future_to_page = {
                        executor.submit(
                            self._generate_single_image,
                            page,
                            task_id,
                            cover_image_data,
                            0,
                            full_outline,
                            compressed_user_images,
                            user_topic
                        ): page
                        for page in other_pages
                    }

                    for page in other_pages:
                        yield {
                            "event": "progress",
                            "data": {
                                "index": page["index"],
                                "status": "generating",
                                "current": len(generated_images) + 1,
                                "total": total,
                                "phase": "content"
                            }
                        }

                    for future in as_completed(future_to_page):
                        page = future_to_page[future]
                        try:
                            index, success, filename, error, _ = future.result()

                            if success:
                                generated_images.append(filename)
                                self._task_states[task_id]["generated"][index] = filename

                                yield {
                                    "event": "complete",
                                    "data": {
                                        "index": index,
                                        "status": "done",
                                        "image_url": f"/api/images/{task_id}/{filename}",
                                        "phase": "content"
                                    }
                                }
                            else:
                                failed_pages.append(page)
                                self._task_states[task_id]["failed"][index] = error

                                yield {
                                    "event": "error",
                                    "data": {
                                        "index": index,
                                        "status": "error",
                                        "message": error,
                                        "retryable": True,
                                        "phase": "content"
                                    }
                                }

                        except Exception as e:
                            failed_pages.append(page)
                            error_msg = str(e)
                            self._task_states[task_id]["failed"][page["index"]] = error_msg

                            yield {
                                "event": "error",
                                "data": {
                                    "index": page["index"],
                                    "status": "error",
                                    "message": error_msg,
                                    "retryable": True,
                                    "phase": "content"
                                }
                            }
            else:
                yield {
                    "event": "progress",
                    "data": {
                        "status": "batch_start",
                        "message": f"开始顺序生成 {len(other_pages)} 页内容...",
                        "current": len(generated_images),
                        "total": total,
                        "phase": "content"
                    }
                }

                for page in other_pages:
                    yield {
                        "event": "progress",
                        "data": {
                            "index": page["index"],
                            "status": "generating",
                            "current": len(generated_images) + 1,
                            "total": total,
                            "phase": "content"
                        }
                    }

                    index, success, filename, error, _ = self._generate_single_image(
                        page,
                        task_id,
                        cover_image_data,
                        0,
                        full_outline,
                        compressed_user_images,
                        user_topic
                    )

                    if success:
                        generated_images.append(filename)
                        self._task_states[task_id]["generated"][index] = filename

                        yield {
                            "event": "complete",
                            "data": {
                                "index": index,
                                "status": "done",
                                "image_url": f"/api/images/{task_id}/{filename}",
                                "phase": "content"
                            }
                        }
                    else:
                        failed_pages.append(page)
                        self._task_states[task_id]["failed"][index] = error

                        yield {
                            "event": "error",
                            "data": {
                                "index": index,
                                "status": "error",
                                "message": error,
                                "retryable": True,
                                "phase": "content"
                            }
                        }

        yield {
            "event": "finish",
            "data": {
                "success": len(failed_pages) == 0,
                "task_id": task_id,
                "images": generated_images,
                "total": total,
                "completed": len(generated_images),
                "failed": len(failed_pages),
                "failed_indices": [p["index"] for p in failed_pages]
            }
        }

    def retry_single_image(
        self,
        task_id: str,
        page: Dict,
        use_reference: bool = True,
        full_outline: str = "",
        user_topic: str = ""
    ) -> Dict[str, Any]:
        """
        重试生成单张图片
        """
        # 仅作为逻辑标识
        self.current_task_dir = os.path.join(self.history_root_dir, task_id)

        reference_image = None
        user_images = None

        if task_id in self._task_states:
            task_state = self._task_states[task_id]
            if use_reference:
                reference_image = task_state.get("cover_image")
            if not full_outline:
                full_outline = task_state.get("full_outline", "")
            if not user_topic:
                user_topic = task_state.get("user_topic", "")
            user_images = task_state.get("user_images")

        # 移除回退到本地文件系统的逻辑
        
        index, success, filename, error, _ = self._generate_single_image(
            page,
            task_id,
            reference_image,
            0,
            full_outline,
            user_images,
            user_topic
        )

        if success:
            if task_id in self._task_states:
                self._task_states[task_id]["generated"][index] = filename
                if index in self._task_states[task_id]["failed"]:
                    del self._task_states[task_id]["failed"][index]

            return {
                "success": True,
                "index": index,
                "image_url": f"/api/images/{task_id}/{filename}"
            }
        else:
            return {
                "success": False,
                "index": index,
                "error": error,
                "retryable": True
            }

    def retry_failed_images(
        self,
        task_id: str,
        pages: List[Dict]
    ) -> Generator[Dict[str, Any], None, None]:
        """
        批量重试失败的图片
        """
        reference_image = None
        if task_id in self._task_states:
            reference_image = self._task_states[task_id].get("cover_image")

        total = len(pages)
        success_count = 0
        failed_count = 0

        yield {
            "event": "retry_start",
            "data": {
                "total": total,
                "message": f"开始重试 {total} 张失败的图片"
            }
        }

        full_outline = ""
        if task_id in self._task_states:
            full_outline = self._task_states[task_id].get("full_outline", "")

        with ThreadPoolExecutor(max_workers=self.MAX_CONCURRENT) as executor:
            future_to_page = {
                executor.submit(
                    self._generate_single_image,
                    page,
                    task_id,
                    reference_image,
                    0,
                    full_outline
                ): page
                for page in pages
            }

            for future in as_completed(future_to_page):
                page = future_to_page[future]
                try:
                    index, success, filename, error, _ = future.result()

                    if success:
                        success_count += 1
                        if task_id in self._task_states:
                            self._task_states[task_id]["generated"][index] = filename
                            if index in self._task_states[task_id]["failed"]:
                                del self._task_states[task_id]["failed"][index]

                        yield {
                            "event": "complete",
                            "data": {
                                "index": index,
                                "status": "done",
                                "image_url": f"/api/images/{task_id}/{filename}"
                            }
                        }
                    else:
                        failed_count += 1
                        yield {
                            "event": "error",
                            "data": {
                                "index": index,
                                "status": "error",
                                "message": error,
                                "retryable": True
                            }
                        }

                except Exception as e:
                    failed_count += 1
                    yield {
                        "event": "error",
                        "data": {
                            "index": page["index"],
                            "status": "error",
                            "message": str(e),
                            "retryable": True
                        }
                    }

        yield {
            "event": "retry_finish",
            "data": {
                "success": failed_count == 0,
                "total": total,
                "completed": success_count,
                "failed": failed_count
            }
        }

    def regenerate_image(
        self,
        task_id: str,
        page: Dict,
        use_reference: bool = True,
        full_outline: str = "",
        user_topic: str = ""
    ) -> Dict[str, Any]:
        """重新生成图片"""
        return self.retry_single_image(
            task_id, page, use_reference,
            full_outline=full_outline,
            user_topic=user_topic
        )

    def get_image_path(self, task_id: str, filename: str) -> str:
        """获取图片逻辑路径（已废弃本地访问，仅返回逻辑路径）"""
        task_dir = os.path.join(self.history_root_dir, task_id)
        return os.path.join(task_dir, filename)

    def get_task_state(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        return self._task_states.get(task_id)

    def cleanup_task(self, task_id: str):
        """清理任务状态"""
        if task_id in self._task_states:
            del self._task_states[task_id]


# 全局服务实例
_service_instance = None

def get_image_service() -> ImageService:
    """获取全局图片生成服务实例"""
    global _service_instance
    if _service_instance is None:
        _service_instance = ImageService()
    return _service_instance

def reset_image_service():
    """重置全局服务实例"""
    global _service_instance
    _service_instance = None
