import os
from typing import Dict

import yaml
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_key: str
    actual_url: str
    actual_password: str
    actual_budget: str
    actual_default_account_id: str
    actual_backup_payee: str
    account_mappings: Dict[str, str]

    class Config:
        env_file = ".env"


def load_config():
    config_path = "/config/config.yml"  # Set default config path
    if not os.path.exists(config_path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_dir, "..", "config", "config.yml")
        if not os.path.exists(config_path):
            raise FileNotFoundError("Configuration file not found at '/config/config.yml'")
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
