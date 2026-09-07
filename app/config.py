from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    portal_base_url: str = "https://urja-ops.flockenergy.tech"
    portal_username: str = ""
    portal_password: str = ""
    cache_ttl_seconds: int = 300
    cache_enabled: bool = True

    auth_enabled: bool = True
    api_username: str = "admin"
    api_password: str = "changeme"
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_expire_minutes: int = 60

    class Config:
        env_file = ".env"


settings = Settings()
