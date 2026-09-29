from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    BACKEND_URL: str = "http://localhost:8000"
    GROQ_API_KEY: str = ""
    AI_SERVICE_TOKEN: str = ""
    AI_MODEL: str = "openai/gpt-oss-120b"


settings = AISettings()
