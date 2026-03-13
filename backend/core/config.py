from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Trading Engine platform"
    VERSION: str = "1.0.0"
    
    # MySQL Database Connection (pymysql is easier to install on macOS without compiling C extensions)
    # Defaulting to localhost, port 3306. Update these once you have your MySQL setup.
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "Vaibhav%408113"
    MYSQL_SERVER: str = "localhost"
    MYSQL_PORT: str = "3306"
    MYSQL_DB: str = "ai_trading"
    
    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_SERVER}:{self.MYSQL_PORT}/{self.MYSQL_DB}"

    # JWT Authentication
    SECRET_KEY: str = "OqEwKzqQpNjH8MKLpIuXzjE4D7B3RkPqT7H6B5N9vXg"  # Example key, must change in prod
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 1 week

    # Multi-Agent Configuration
    LLM_API_KEY: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
