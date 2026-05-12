from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str = Field(...)
    llm_model: str = "llama-3.3-70b-versatile"

    language_tool_locale: str = "en-US"
    spacy_model: str = "en_core_web_sm"

    max_regeneration_attempts: int = 3
    max_validator_tool_calls: int = 8

    explanation_level: str = "B2"


config = Config()
