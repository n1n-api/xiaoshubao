"""
大纲生成相关 API 路由

包含功能：
- 生成大纲（支持图片上传）
"""

import time
import base64
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, request, Response, stream_with_context
from backend.services.outline import get_outline_service
from .utils import log_request, log_error

logger = logging.getLogger(__name__)


def create_outline_blueprint():
    """创建大纲路由蓝图（工厂函数，支持多次调用）"""
    outline_bp = Blueprint('outline', __name__)

    @outline_bp.route('/outline', methods=['POST'])
    def generate_outline():
        """
        生成大纲（支持图片上传）
        
        改为 SSE 流式响应以防止 Cloudflare 524 超时
        """
        start_time = time.time()
        
        # 解析请求数据 (需要在主线程完成)
        try:
            topic, images = _parse_outline_request()
            log_request('/outline', {'topic': topic, 'images': images})
            
            if not topic:
                return Response(
                    "event: error\ndata: 参数错误：topic 不能为空\n\n", 
                    mimetype='text/event-stream'
                )

        except Exception as e:
            return Response(
                f"event: error\ndata: 请求解析失败: {str(e)}\n\n",
                mimetype='text/event-stream'
            )

        def generate():
            executor = ThreadPoolExecutor(max_workers=1)
            try:
                # 在线程中运行耗时任务
                logger.info(f"🔄 开始生成大纲 (后台线程)，主题: {topic[:50]}...")
                
                outline_service = get_outline_service()
                future = executor.submit(outline_service.generate_outline, topic, images if images else None)
                
                # 循环等待任务完成，期间发送心跳
                while not future.done():
                    yield ": keep-alive\n\n"
                    time.sleep(5)  # 每5秒发送一次心跳
                
                # 获取结果
                result = future.result()
                elapsed = time.time() - start_time
                
                if result["success"]:
                    logger.info(f"✅ 大纲生成成功，耗时 {elapsed:.2f}s")
                    # 序列化结果
                    json_result = json.dumps(result, ensure_ascii=False)
                    yield f"event: complete\ndata: {json_result}\n\n"
                else:
                    logger.error(f"❌ 大纲生成失败: {result.get('error')}")
                    error_msg = result.get('error', '未知错误').replace('\n', '\\n')
                    yield f"event: error\ndata: {error_msg}\n\n"

            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                log_error('/outline', f"{str(e)}\nStack Trace:\n{error_trace}")
                error_msg = str(e).replace('\n', '\\n')
                yield f"event: error\ndata: 大纲生成异常: {error_msg}\n\n"
            finally:
                executor.shutdown(wait=False)

        return Response(stream_with_context(generate()), mimetype='text/event-stream')

    return outline_bp


def _parse_outline_request():
    """
    解析大纲生成请求

    支持两种格式：
    1. multipart/form-data - 用于文件上传
    2. application/json - 用于 base64 图片

    返回：
        tuple: (topic, images) - 主题和图片列表
    """
    # 检查是否是 multipart/form-data（带图片文件）
    if request.content_type and 'multipart/form-data' in request.content_type:
        topic = request.form.get('topic')
        images = []

        # 获取上传的图片文件
        if 'images' in request.files:
            files = request.files.getlist('images')
            for file in files:
                if file and file.filename:
                    image_data = file.read()
                    images.append(image_data)

        return topic, images

    # JSON 请求（无图片或 base64 图片）
    data = request.get_json()
    topic = data.get('topic')
    images = []

    # 支持 base64 格式的图片
    images_base64 = data.get('images', [])
    if images_base64:
        for img_b64 in images_base64:
            # 移除可能的 data URL 前缀
            if ',' in img_b64:
                img_b64 = img_b64.split(',')[1]
            images.append(base64.b64decode(img_b64))

    return topic, images
