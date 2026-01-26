from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import EmailStr

class Settings(BaseSettings):
    EMAIL_USER_NAME: EmailStr
    EMAIL_PASSWORD: str
    IMAP_SERVER: str = "imap.gmail.com"
    GROQ_API_KEY: str
    model_config = SettingsConfigDict(env_file=".env",env_file_encoding='utf-8')
    AUTO_EXECUTE_THRESHOLD: float = 0.9
    REVIEW_THRESHOLD: float = 0.6
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    DB_HOST: str = "localhost"
    DB_NAME: str = "email_agent_db"
    DB_USER: str = "postgres"
    DB_PASSWORD: str
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_PHONE_NUMBER: str
    TARGET_PHONE_NUMBER: str
    TRELLO_API_KEY: str
    TRELLO_API_TOKEN: str
    TOKEN_PATH: str = "token.json"
    TRELLO_LIST_ID: str
    model_config = SettingsConfigDict(env_file=".env",env_file_encoding='utf-8')
settings = Settings()