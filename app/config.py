from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Bid Risk Manager"
    database_url: str = "sqlite:///./bids.db"
    log_level: str = "INFO"
    log_file: str = "app.log"
    bids_csv_path: str = "data/bids.csv"
    # Risk rules
    risk_margin_threshold: float = 0.15  # margin below 15% is risky
    risk_deadline_days: int = 7  # deadline within 7 days is risky
    risk_lost_bids: int = 2  # client with 2 or more lost bids is risky

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()