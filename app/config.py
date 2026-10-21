from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Bid Risk Manager"
    database_url: str = "sqlite:///./bids.db"
    log_level: str = "INFO"
    log_file: str = "app.log"
    bids_csv_path: str = "data/bids.csv"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()