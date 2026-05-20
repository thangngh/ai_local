from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    project_root: Path = Path.cwd()
    configs_dir: Path = Path("configs")

    model_config = SettingsConfigDict(env_prefix="AI_LOCAL_")

