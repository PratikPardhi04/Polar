from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "POLARIS"
    APP_ENV: str = "demo"
    DATABASE_URL: str = "postgresql+psycopg2://polaris:polaris@localhost:5432/polaris"
    JWT_SECRET_KEY: str = "change-me-exp-46isea-2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"


settings = Settings()
