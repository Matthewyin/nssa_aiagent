"""
配置管理器
支持配置文件热加载和缓存管理
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional
from loguru import logger
from .config_loader import load_yaml_config, get_config_dir


class ConfigManager:
    """配置管理器，支持热加载"""
    
    def __init__(self):
        """初始化配置管理器"""
        self._config_cache: Dict[str, Dict[str, Any]] = {}
        self._file_timestamps: Dict[str, float] = {}
        self._llm_instances: Dict[str, Any] = {}  # 缓存 LLM 实例
        logger.info("配置管理器已初始化")
    
    def load_config(self, config_name: str) -> Dict[str, Any]:
        """
        加载配置，检查文件是否修改
        
        Args:
            config_name: 配置名称（如 'llm_config', 'agent_config'）
            
        Returns:
            配置字典
        """
        config_path = get_config_dir() / f"{config_name}.yaml"
        
        if not config_path.exists():
            logger.error(f"配置文件不存在: {config_path}")
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        current_mtime = os.path.getmtime(config_path)
        
        # 检查文件是否修改
        if config_name not in self._file_timestamps or \
           self._file_timestamps[config_name] != current_mtime:
            # 重新加载配置
            logger.info(f"正在重新加载配置: {config_name}")
            self._config_cache[config_name] = load_yaml_config(config_path)
            self._file_timestamps[config_name] = current_mtime
            logger.info(f"配置 {config_name} 已重新加载")
            
            # 清除相关的 LLM 实例缓存
            if config_name == "llm_config":
                self._llm_instances.clear()
                logger.info("LLM 实例缓存已清除，下次调用时将使用新配置创建")
        
        return self._config_cache[config_name]
    
    def invalidate_cache(self, config_name: str):
        """
        使配置缓存失效
        
        Args:
            config_name: 配置名称
        """
        if config_name in self._config_cache:
            del self._config_cache[config_name]
            logger.info(f"配置缓存已失效: {config_name}")
        
        if config_name in self._file_timestamps:
            del self._file_timestamps[config_name]
        
        # 如果是 LLM 配置，清除 LLM 实例缓存
        if config_name == "llm_config":
            self._llm_instances.clear()
            logger.info("LLM 实例缓存已清除")
    
    def get_llm(self, instance_name: str = "default", force_reload: bool = False):
        """
        获取 LLM 实例，支持强制重载
        
        Args:
            instance_name: 实例名称
            force_reload: 是否强制重载
            
        Returns:
            LLM 实例
        """
        if force_reload or instance_name not in self._llm_instances:
            # 延迟导入，避免在未安装某些依赖时影响其他功能
            config = self.load_config("llm_config")
            llm_config = config.get("llm", {}) or {}
            providers_conf = config.get("providers", {}) or {}

            provider = llm_config.get("provider", "ollama").lower()

            # 1. 先从 llm 节点读通用参数
            model = llm_config.get("model")
            base_url = llm_config.get("base_url")
            temperature = llm_config.get("temperature", 0.7)
            max_tokens = llm_config.get("max_tokens")
            timeout = llm_config.get("timeout")
            api_key = llm_config.get("api_key")

            # 2. 再从 providers.<provider> 读取默认值（如有）
            provider_conf = providers_conf.get(provider, {}) or {}
            if model is None:
                model = provider_conf.get("model")
            if base_url is None:
                base_url = provider_conf.get("base_url")
            if api_key is None:
                api_key = provider_conf.get("api_key")

            # 3. 根据 provider 构造对应的 LLM 实例
            llm_instance = None

            if provider == "ollama":
                from langchain_community.llms import Ollama

                llm_instance = Ollama(
                    model=model,
                    base_url=base_url,
                    temperature=temperature,
                )

            elif provider == "openai":
                try:
                    from langchain_openai import ChatOpenAI
                except ImportError as e:
                    raise ImportError(
                        "使用 provider='openai' 需要安装 'langchain-openai' 依赖，请先通过包管理器安装"
                    ) from e

                # base_url 可选（例如自定义 OpenAI 兼容网关）
                llm_kwargs = {
                    "model": model,
                    "temperature": temperature,
                }
                if max_tokens is not None:
                    llm_kwargs["max_tokens"] = max_tokens
                if timeout is not None:
                    llm_kwargs["timeout"] = timeout
                if base_url:
                    llm_kwargs["base_url"] = base_url
                if api_key:
                    # 显式传入 api_key，优先使用配置/环境变量解析后的值
                    llm_kwargs["api_key"] = api_key

                llm_instance = ChatOpenAI(**llm_kwargs)

            elif provider == "gemini":
                try:
                    from langchain_google_genai import ChatGoogleGenerativeAI
                except ImportError as e:
                    raise ImportError(
                        "使用 provider='gemini' 需要安装 'langchain-google-genai' 依赖，请先通过包管理器安装"
                    ) from e

                llm_kwargs = {
                    "model": model,
                    "temperature": temperature,
                }
                if max_tokens is not None:
                    llm_kwargs["max_output_tokens"] = max_tokens
                if timeout is not None:
                    llm_kwargs["timeout"] = timeout

                if api_key:
                    # ChatGoogleGenerativeAI 支持通过 api_key 显式传入凭证
                    llm_kwargs["api_key"] = api_key

                llm_instance = ChatGoogleGenerativeAI(**llm_kwargs)

            elif provider == "deepseek":
                # DeepSeek 通过 OpenAI 兼容接口访问
                try:
                    from langchain_openai import ChatOpenAI
                except ImportError as e:
                    raise ImportError(
                        "使用 provider='deepseek' 需要安装 'langchain-openai' 依赖，请先通过包管理器安装"
                    ) from e

                llm_kwargs = {
                    "model": model,
                    "temperature": temperature,
                }
                if max_tokens is not None:
                    llm_kwargs["max_tokens"] = max_tokens
                if timeout is not None:
                    llm_kwargs["timeout"] = timeout
                if base_url:
                    llm_kwargs["base_url"] = base_url
                if api_key:
                    # DeepSeek 使用独立的 DEEPSEEK_API_KEY 时显式传入
                    # 若未配置 api_key，则回退由 ChatOpenAI 
                    # 自行从 OPENAI_API_KEY 等环境变量读取
                    llm_kwargs["api_key"] = api_key

                llm_instance = ChatOpenAI(**llm_kwargs)

            else:
                raise ValueError(f"暂不支持的 LLM provider: {provider}")

            self._llm_instances[instance_name] = llm_instance
            logger.info(
                f"LLM 实例已创建: {instance_name}, provider: {provider}, model: {getattr(llm_instance, 'model_name', None) or model}"
            )
        
        return self._llm_instances[instance_name]
    
    def clear_llm_cache(self):
        """清除所有 LLM 实例缓存"""
        self._llm_instances.clear()
        logger.info("所有 LLM 实例缓存已清除")
    
    def get_cached_configs(self) -> list:
        """获取已缓存的配置列表"""
        return list(self._config_cache.keys())


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

