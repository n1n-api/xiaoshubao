"""
配置管理相关 API 路由

包含功能：
- 获取当前配置
- 更新配置
- 测试服务商连接
"""

import logging
from pathlib import Path
import yaml
from flask import Blueprint, request, jsonify
from .utils import prepare_providers_for_response, mask_api_key

logger = logging.getLogger(__name__)

# 配置文件路径
CONFIG_DIR = Path(__file__).parent.parent.parent
IMAGE_CONFIG_PATH = CONFIG_DIR / 'image_providers.yaml'
TEXT_CONFIG_PATH = CONFIG_DIR / 'text_providers.yaml'


def create_config_blueprint():
    """创建配置路由蓝图（工厂函数，支持多次调用）"""
    config_bp = Blueprint('config', __name__)

    # ==================== 配置读写 ====================

    @config_bp.route('/config', methods=['GET'])
    def get_config():
        """
        获取当前配置
        
        返回：
        - success: 是否成功
        - config: 配置对象
          - text_generation: 文本生成配置
          - image_generation: 图片生成配置
        """
        try:
            # 1. 尝试从数据库加载
            from backend.utils.config_manager import config_manager
            
            image_providers_data = {}
            text_providers_data = {}
            
            if config_manager.engine:
                image_providers_data = config_manager.get_config('image_providers') or {}
                text_providers_data = config_manager.get_config('text_providers') or {}
            
            # 2. 读取本地配置文件作为默认值/回退
            image_config_default = _read_config(IMAGE_CONFIG_PATH, {
                'active_provider': 'google_genai',
                'providers': {}
            })
            text_config_default = _read_config(TEXT_CONFIG_PATH, {
                'active_provider': 'google_gemini',
                'providers': {}
            })
            
            # 3. 合并配置（数据库优先）
            if not image_providers_data:
                image_providers_data = image_config_default
            
            if not text_providers_data:
                text_providers_data = text_config_default
                
            # 获取存储配置
            storage_config = config_manager.get_config('storage_config') or {}

            return jsonify({
                "success": True,
                "config": {
                    "text_generation": {
                        "active_provider": text_providers_data.get('active_provider', ''),
                        "providers": prepare_providers_for_response(
                            text_providers_data.get('providers', {})
                        )
                    },
                    "image_generation": {
                        "active_provider": image_providers_data.get('active_provider', ''),
                        "providers": prepare_providers_for_response(
                            image_providers_data.get('providers', {})
                        )
                    },
                    "storage": {
                        "endpoint_url": storage_config.get('endpoint_url', ''),
                        "access_key_id": mask_api_key(storage_config.get('access_key_id', '')),
                        "bucket_name": storage_config.get('bucket_name', ''),
                        "public_domain": storage_config.get('public_domain', '')
                    }
                }
            })

        except Exception as e:
            logger.error(f"获取配置失败: {str(e)}")
            return jsonify({
                "success": False,
                "error": f"获取配置失败: {str(e)}"
            }), 500

    @config_bp.route('/config', methods=['POST'])
    def update_config():
        """
        更新配置
        """
        try:
            data = request.get_json()
            from backend.utils.config_manager import config_manager

            # 更新图片生成配置
            if 'image_generation' in data:
                new_data = data['image_generation']
                if config_manager.engine:
                    # 数据库模式：需要合并逻辑
                    # 1. 读取旧配置
                    old_data = config_manager.get_config('image_providers') or {}
                    
                    # 2. 合并 active_provider
                    if 'active_provider' in new_data:
                        old_data['active_provider'] = new_data['active_provider']
                    
                    # 3. 合并 providers
                    if 'providers' in new_data:
                        old_providers = old_data.get('providers', {})
                        new_providers = new_data['providers']
                        
                        for name, new_provider_config in new_providers.items():
                            # 如果新配置的 api_key 为空/假值，保留旧的
                            if not new_provider_config.get('api_key'):
                                if name in old_providers and old_providers[name].get('api_key'):
                                    new_provider_config['api_key'] = old_providers[name]['api_key']
                                else:
                                    # 如果旧的也没有，删除这个键，避免存入 null/空串
                                    new_provider_config.pop('api_key', None)
                            
                            # 移除不需要保存的字段
                            new_provider_config.pop('api_key_masked', None)
                            new_provider_config.pop('api_key_env', None)

                        old_data['providers'] = new_providers
                    
                    config_manager.save_config('image_providers', old_data)
                else:
                    _update_provider_config(IMAGE_CONFIG_PATH, new_data)

            # 更新文本生成配置
            if 'text_generation' in data:
                new_data = data['text_generation']
                if config_manager.engine:
                    # 数据库模式：需要合并逻辑
                    # 1. 读取旧配置
                    old_data = config_manager.get_config('text_providers') or {}
                    
                    # 2. 合并 active_provider
                    if 'active_provider' in new_data:
                        old_data['active_provider'] = new_data['active_provider']
                    
                    # 3. 合并 providers
                    if 'providers' in new_data:
                        old_providers = old_data.get('providers', {})
                        new_providers = new_data['providers']
                        
                        for name, new_provider_config in new_providers.items():
                            # 如果新配置的 api_key 为空/假值，保留旧的
                            if not new_provider_config.get('api_key'):
                                if name in old_providers and old_providers[name].get('api_key'):
                                    new_provider_config['api_key'] = old_providers[name]['api_key']
                                else:
                                    # 如果旧的也没有，删除这个键
                                    new_provider_config.pop('api_key', None)

                            # 移除不需要保存的字段
                            new_provider_config.pop('api_key_masked', None)
                            new_provider_config.pop('api_key_env', None)

                        old_data['providers'] = new_providers

                    config_manager.save_config('text_providers', old_data)
                else:
                    _update_provider_config(TEXT_CONFIG_PATH, new_data)
            
            # 更新存储配置
            if 'storage' in data and config_manager.engine:
                storage_data = data['storage']
                # 如果 access_key_id 是 masked 的，保留原值
                current_storage = config_manager.get_config('storage_config') or {}
                if storage_data.get('access_key_id') and '*' in storage_data.get('access_key_id'):
                     storage_data['access_key_id'] = current_storage.get('access_key_id')
                     storage_data['secret_access_key'] = current_storage.get('secret_access_key')
                
                config_manager.save_config('storage_config', storage_data)

            # 清除配置缓存
            _clear_config_cache()

            return jsonify({
                "success": True,
                "message": "配置已保存"
            })

        except Exception as e:
            return jsonify({
                "success": False,
                "error": f"更新配置失败: {str(e)}"
            }), 500

    # ==================== 连接测试 ====================

    @config_bp.route('/config/test', methods=['POST'])
    def test_connection():
        """
        测试服务商连接

        请求体：
        - type: 服务商类型（google_genai/google_gemini/openai_compatible/image_api）
        - provider_name: 服务商名称（用于从配置读取 API Key）
        - api_key: API Key（可选，若不提供则从配置读取）
        - base_url: Base URL（可选）
        - model: 模型名称（可选）

        返回：
        - success: 是否成功
        - message: 测试结果消息
        """
        try:
            data = request.get_json()
            provider_type = data.get('type')
            provider_name = data.get('provider_name')

            if not provider_type:
                return jsonify({"success": False, "error": "缺少 type 参数"}), 400

            # 构建配置
            config = {
                'api_key': data.get('api_key'),
                'base_url': data.get('base_url'),
                'model': data.get('model')
            }

            # 如果没有提供 api_key，从配置文件读取
            if not config['api_key'] and provider_name:
                config = _load_provider_config(provider_type, provider_name, config)

            if not config['api_key']:
                return jsonify({"success": False, "error": "API Key 未配置"}), 400

            # 根据类型执行测试
            result = _test_provider_connection(provider_type, config)
            return jsonify(result), 200 if result['success'] else 400

        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    return config_bp


# ==================== 辅助函数 ====================

def _read_config(path: Path, default: dict) -> dict:
    """读取配置文件"""
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or default
    return default


def _write_config(path: Path, config: dict):
    """写入配置文件"""
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)


def _update_provider_config(config_path: Path, new_data: dict):
    """
    更新服务商配置

    Args:
        config_path: 配置文件路径
        new_data: 新的配置数据
    """
    # 读取现有配置
    existing_config = _read_config(config_path, {'providers': {}})

    # 更新 active_provider
    if 'active_provider' in new_data:
        existing_config['active_provider'] = new_data['active_provider']

    # 更新 providers
    if 'providers' in new_data:
        existing_providers = existing_config.get('providers', {})
        new_providers = new_data['providers']

        for name, new_provider_config in new_providers.items():
            # 如果新配置的 api_key 是空的，保留原有的
            if new_provider_config.get('api_key') in [True, False, '', None]:
                if name in existing_providers and existing_providers[name].get('api_key'):
                    new_provider_config['api_key'] = existing_providers[name]['api_key']
                else:
                    new_provider_config.pop('api_key', None)

            # 移除不需要保存的字段
            new_provider_config.pop('api_key_env', None)
            new_provider_config.pop('api_key_masked', None)

        existing_config['providers'] = new_providers

    # 保存配置
    _write_config(config_path, existing_config)


def _clear_config_cache():
    """清除配置缓存"""
    try:
        from backend.config import Config
        Config._image_providers_config = None
    except Exception:
        pass

    try:
        from backend.services.image import reset_image_service
        reset_image_service()
    except Exception:
        pass


def _load_provider_config(provider_type: str, provider_name: str, config: dict) -> dict:
    """
    从配置文件加载服务商配置

    Args:
        provider_type: 服务商类型
        provider_name: 服务商名称
        config: 当前配置（会被合并）

    Returns:
        dict: 合并后的配置
    """
    # 确定配置文件路径
    if provider_type in ['openai_compatible', 'google_gemini']:
        config_path = TEXT_CONFIG_PATH
    else:
        config_path = IMAGE_CONFIG_PATH

    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            yaml_config = yaml.safe_load(f) or {}
            providers = yaml_config.get('providers', {})

            if provider_name in providers:
                saved = providers[provider_name]
                config['api_key'] = saved.get('api_key')

                if not config['base_url']:
                    config['base_url'] = saved.get('base_url')
                if not config['model']:
                    config['model'] = saved.get('model')

    return config


def _test_provider_connection(provider_type: str, config: dict) -> dict:
    """
    测试服务商连接

    Args:
        provider_type: 服务商类型
        config: 服务商配置

    Returns:
        dict: 测试结果
    """
    test_prompt = "请回复'你好'"

    if provider_type == 'google_genai':
        return _test_google_genai(config)

    elif provider_type == 'google_gemini':
        return _test_google_gemini(config, test_prompt)

    elif provider_type == 'openai_compatible':
        return _test_openai_compatible(config, test_prompt)

    elif provider_type == 'image_api':
        return _test_image_api(config)

    else:
        raise ValueError(f"不支持的类型: {provider_type}")


def _test_google_genai(config: dict) -> dict:
    """测试 Google GenAI 图片生成服务"""
    from google import genai

    if config.get('base_url'):
        client = genai.Client(
            api_key=config['api_key'],
            http_options={
                'base_url': config['base_url'],
                'api_version': 'v1beta'
            },
            vertexai=False
        )
        # 测试列出模型
        try:
            list(client.models.list())
            return {
                "success": True,
                "message": "连接成功！仅代表连接稳定，不确定是否可以稳定支持图片生成"
            }
        except Exception as e:
            raise Exception(f"连接测试失败: {str(e)}")
    else:
        return {
            "success": True,
            "message": "Vertex AI 无法通过 API Key 测试连接（需要 OAuth2 认证）。请在实际生成图片时验证配置是否正确。"
        }


def _test_google_gemini(config: dict, test_prompt: str) -> dict:
    """测试 Google Gemini 文本生成服务"""
    from google import genai

    if config.get('base_url'):
        client = genai.Client(
            api_key=config['api_key'],
            http_options={
                'base_url': config['base_url'],
                'api_version': 'v1beta'
            },
            vertexai=False
        )
    else:
        client = genai.Client(
            api_key=config['api_key'],
            vertexai=True
        )

    model = config.get('model') or 'gemini-2.0-flash-exp'
    response = client.models.generate_content(
        model=model,
        contents=test_prompt
    )
    result_text = response.text if hasattr(response, 'text') else str(response)

    return _check_response(result_text)


def _test_openai_compatible(config: dict, test_prompt: str) -> dict:
    """测试 OpenAI 兼容接口"""
    import requests

    base_url = config['base_url'].rstrip('/').rstrip('/v1') if config.get('base_url') else 'https://api.openai.com'
    url = f"{base_url}/v1/chat/completions"

    payload = {
        "model": config.get('model') or 'gpt-3.5-turbo',
        "messages": [{"role": "user", "content": test_prompt}],
        "max_tokens": 50
    }

    response = requests.post(
        url,
        headers={
            'Authorization': f"Bearer {config['api_key']}",
            'Content-Type': 'application/json'
        },
        json=payload,
        timeout=30
    )

    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")

    result = response.json()
    result_text = result['choices'][0]['message']['content']

    return _check_response(result_text)


def _test_image_api(config: dict) -> dict:
    """测试图片 API 连接"""
    import requests

    base_url = config['base_url'].rstrip('/').rstrip('/v1') if config.get('base_url') else 'https://api.openai.com'
    url = f"{base_url}/v1/models"

    response = requests.get(
        url,
        headers={'Authorization': f"Bearer {config['api_key']}"},
        timeout=30
    )

    if response.status_code == 200:
        return {
            "success": True,
            "message": "连接成功！仅代表连接稳定，不确定是否可以稳定支持图片生成"
        }
    else:
        raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")


def _check_response(result_text: str) -> dict:
    """检查响应是否符合预期"""
    # 放宽检查条件，只要有响应文本就算成功
    # 很多模型可能不会严格回复"你好，红墨"，而是回复"你好！我是xxx"
    if result_text and len(result_text.strip()) > 0:
        return {
            "success": True,
            "message": f"连接成功！响应: {result_text[:100]}"
        }
    else:
        return {
            "success": False,  # 空响应算作失败
            "message": f"连接成功，但响应内容为空"
        }
