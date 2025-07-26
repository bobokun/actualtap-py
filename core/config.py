from pathlib import Path
from typing import Dict
from typing import Optional

import yaml
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_key: str
    actual_url: str
    actual_password: str
    actual_encryption_password: Optional[str] = None
    actual_budget: str
    actual_default_account_id: str
    actual_backup_payee: str
    account_mappings: Dict[str, str]
    log_level: str = "INFO"

    class Config:
        env_file = ".env"


# Define config_path globally
config_path = Path("/config/config.yml")  # Set default config path
base_dir = Path(__file__).resolve().parent
fallback_config_path = base_dir / ".." / "config" / "config.yml"
if not config_path.exists():
    config_path = fallback_config_path
    if not config_path.exists():
        raise FileNotFoundError("Configuration file not found at '/config/config.yml'")


def load_config():
    with open(config_path) as file:
        config = yaml.safe_load(file)
        if not config:
            raise ValueError("Empty configuration file")
        return Settings(**config)


settings = load_config()


def redact_sensitive_settings(keys_to_redact: list, redaction_placeholder: str = "REDACTED"):
    settings_dict = settings.dict()
    for key in keys_to_redact:
        if key in settings_dict:
            settings_dict[key] = redaction_placeholder  # Redact the value
    return settings_dict
