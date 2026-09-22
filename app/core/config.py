from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Expensio API"
    app_env: str = "development"

    database_url: str

    firebase_project_id: str | None = None
    firebase_credentials_path: str = "firebase-service-account.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()