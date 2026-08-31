from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", ".env.local"), env_prefix="PDP_", extra="ignore")

    app_name: str = "消费者运营中台"
    environment: str = "dev"
    database_url: str = "sqlite:///./pdp.db"
    redis_url: str = "redis://localhost:6379/0"
    default_tenant_id: str = "tenant-default"

    llm_default_model: str = "hunyuan-pro"
    llm_default_base_url: str = "https://api.hunyuan.cloud.tencent.com/v1"
    llm_default_api_key: str = ""

    llm_lite_model: str = "hunyuan-lite"
    llm_lite_base_url: str = "https://api.hunyuan.cloud.tencent.com/v1"
    llm_lite_api_key: str = ""

    llm_fallback_model: str = "deepseek-chat"
    llm_fallback_base_url: str = "https://api.deepseek.com/v1"
    llm_fallback_api_key: str = ""

    llm_local_enabled: bool = False
    llm_local_model: str = "qwen2.5:3b"
    llm_local_base_url: str = "http://localhost:11434/v1"

    embedding_provider: str = "local"
    embedding_model: str = "bge-m3"
    embedding_base_url: str = "http://localhost:11434/v1"

    flywheel_auto_enabled: bool = False
    flywheel_interval_minutes: int = 10

    auth_secret: str = "dev-secret-change-me"
    admin_username: str = "admin"
    admin_password: str = "admin123"

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    admin_static_dir: str = "../web/dist"

    # 飞书自建应用接入（凭据来自飞书开放平台）
    feishu_enabled: bool = False
    feishu_mock: bool = True
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_chat_id: str = ""
    feishu_command_prefix: str = "@运营中台"



@lru_cache
def get_settings() -> Settings:
    return Settings()
