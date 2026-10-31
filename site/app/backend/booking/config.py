from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://booking:booking@localhost:5433/booking"
    cors_origins: str = "*"
    agent_url: str | None = None
    agent_timeout: float = 60


settings = Settings()
