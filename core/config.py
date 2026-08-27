from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional

import yaml
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import field_validator
from pydantic import model_validator
from pydantic_settings import BaseSettings


class AccountMapping(BaseModel):
    """A single Tap-to-Pay account mapping.

    ``account_id`` is the Actual account UUID. ``topup`` is the top-up
    multiplier for that account (0 = disabled). See ``apply_topup`` in
    ``services.actual_service`` for the exact math.
    """

    account_id: str
    topup: int = 0

    @field_validator("topup", mode="before")
    def validate_topup(cls, v):
        if v is None or v == "":
            return 0
        try:
            topup = int(v)
        except (TypeError, ValueError):
            raise ValueError("topup must be an integer (0 = disabled, 1 = 1x, 2 = 2x, ...)")
        if topup < 0:
            raise ValueError("topup cannot be negative")
        return topup


def _coerce_account_mappings(mappings):
    """Normalize a mapping dict so values become ``AccountMapping``.

    Accepts the short ``"Card Name": "uuid"`` form as well as the explicit
    ``"Card Name": {account_id: "uuid", topup: 1}`` form.
    """
    if not mappings:
        return {}
    normalized = {}
    for name, value in mappings.items():
        if isinstance(value, AccountMapping):
            normalized[name] = value
        elif isinstance(value, str):
            normalized[name] = AccountMapping(account_id=value)
        elif isinstance(value, dict):
            normalized[name] = AccountMapping(**value)
        else:
            raise ValueError(f"Invalid account mapping for '{name}'. Expected a UUID string or an object with 'account_id'.")
    return normalized


class BudgetConfig(BaseModel):
    """A budget (by name or Sync ID) with its own account mappings.

    Set ``default: true`` on exactly one budget to make it receive cards
    that are not mapped anywhere; that budget's ``default_account_id`` is
    used for them.
    """

    name_or_sync_id: str
    default: bool = False
    default_account_id: Optional[str] = None
    account_mappings: Dict[str, AccountMapping] = {}

    @field_validator("account_mappings", mode="before")
    def coerce_mappings(cls, v):
        return _coerce_account_mappings(v)


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    api_key: str
    actual_url: str
    actual_password: str
    actual_encryption_password: Optional[str] = None
    actual_backup_payee: str
    # The only routing structure. Every budget has its own account
    # mappings; one budget may set ``default: true`` to absorb unmapped
    # cards via its ``default_account_id``.
    budgets: List[BudgetConfig]
    log_level: str = "INFO"

    @field_validator("budgets")
    def budgets_not_empty(cls, v):
        if not v:
            raise ValueError("At least one budget must be configured under 'budgets'.")
        return v

    @model_validator(mode="after")
    def validate_default_budget(self):
        defaults = [b for b in self.budgets if b.default]
        if len(defaults) > 1:
            raise ValueError("Only one budget can be marked as 'default: true'.")
        if defaults and not defaults[0].default_account_id:
            raise ValueError("The default budget must define 'default_account_id'.")
        return self

    @property
    def default_budget(self) -> Optional[BudgetConfig]:
        for budget in self.budgets:
            if budget.default:
                return budget
        return None


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
    settings_dict = settings.model_dump()
    for key in keys_to_redact:
        if key in settings_dict:
            settings_dict[key] = redaction_placeholder  # Redact the value
    return settings_dict
