from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "s1421_doc"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

SHORT_TERM_N = 12
SUMMARIZE_EVERY_USER_MSGS = 5
EPISODE_TOP_K = 3
LIFETIME_EVERY = 2
COMPRESS_KEEP = 4
COMPRESS_CHARS = 36
