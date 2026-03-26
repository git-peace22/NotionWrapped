"""
Unified config — reads from .env and config/settings.yaml.
"""

import yaml
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NotionConfig:
    mcp_server_command: str = "npx"
    mcp_server_args: list[str] = ["-y", "@notionhq/notion-mcp-server"]


class AgentConfig:
    model: str = "gemini-2.0-flash"
    max_tokens: int = 4096
    batch_size: int = 10


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    notion_api_token: str = Field("", alias="NOTION_API_TOKEN")
    groq_api_key: str = Field(..., alias="GROQ_API_KEY")

    # OAuth (public integration)
    notion_oauth_client_id: str = Field("", alias="NOTION_OAUTH_CLIENT_ID")
    notion_oauth_client_secret: str = Field("", alias="NOTION_OAUTH_CLIENT_SECRET")
    redirect_uri: str = Field("http://localhost:8000/auth/callback", alias="REDIRECT_URI")

    # Populated from YAML below
    notion: NotionConfig = NotionConfig()
    agent: AgentConfig = AgentConfig()


def _load_yaml_config() -> dict:
    yaml_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    if yaml_path.exists():
        with open(yaml_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def _build_settings() -> Settings:
    s = Settings()
    yaml_cfg = _load_yaml_config()

    if "notion" in yaml_cfg:
        for k, v in yaml_cfg["notion"].items():
            setattr(s.notion, k, v)

    if "agent" in yaml_cfg:
        for k, v in yaml_cfg["agent"].items():
            setattr(s.agent, k, v)

    return s


settings = _build_settings()
