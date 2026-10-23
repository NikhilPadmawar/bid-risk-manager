from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Bid Risk Manager"
    database_url: str = "sqlite:///./bids.db"
    log_level: str = "INFO"
    log_file: str = "app.log"
    bids_csv_path: str = "data/bids.csv"

    # Risk rules (story 1 of phase 2)
    risk_margin_threshold: float = 0.15  # margin below 15% is risky
    risk_deadline_days: int = 7  # deadline within 7 days is risky
    risk_lost_bids: int = 2  # client with 2 or more lost bids is risky

    # LLM through OpenRouter (story 3 of phase 2)
    openrouter_api_key: SecretStr = SecretStr("")  # secret: set it in .env only
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "anthropic/claude-haiku-5.5"
    llm_temperature: float = 0.0
    llm_timeout_seconds: int = 60

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()