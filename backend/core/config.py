from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Trading Engine"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"

    # Deployment / demo mode
    APP_ENV: str = "development"

    # Database configuration
    DATABASE_URL: str | None = None
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_SERVER: str = "localhost"
    MYSQL_PORT: str = "3306"
    MYSQL_DB: str = "ai_trading"
    SQLITE_DB_PATH: str = "backend/ai_trading.db"

    # JWT Authentication
    SECRET_KEY: str = "change-me-for-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # CORS
    FRONTEND_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Market data providers
    UPSTOX_ACCESS_TOKEN: str = ""
    UPSTOX_BASE_URL: str = "https://api.upstox.com"
    UPSTOX_NSE_INSTRUMENTS_URL: str = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
    UPSTOX_BSE_INSTRUMENTS_URL: str = "https://assets.upstox.com/market-quote/instruments/exchange/BSE.json.gz"
    TWELVE_DATA_API_KEY: str = ""
    TWELVE_DATA_BASE_URL: str = "https://api.twelvedata.com"

    # Optional AI integrations
    LLM_API_KEY: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def resolved_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL

        if self.MYSQL_PASSWORD:
            return (
                f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
                f"@{self.MYSQL_SERVER}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
            )

        sqlite_path = Path(self.SQLITE_DB_PATH)
        if not sqlite_path.is_absolute():
            project_root = Path(__file__).resolve().parents[2]
            sqlite_path = project_root / sqlite_path
        return f"sqlite:///{sqlite_path.resolve().as_posix()}"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.FRONTEND_ORIGINS.split(",") if origin.strip()]


settings = Settings()
