"""macOS Keychain-backed secret storage."""

from __future__ import annotations

from dataclasses import dataclass

from aiquotabar.config import log, save_config

SERVICE_NAME = "AIQuotaBar"
SECRET_KEYS = frozenset({
    "cookie_str",
    "chatgpt_cookies",
    "copilot_cookies",
    "cursor_cookies",
    "openai_key",
    "minimax_key",
    "glm_key",
})

_runtime_cache: dict[str, str] = {}


class SecretStoreError(RuntimeError):
    """Raised when the Keychain backend is unavailable or rejects access."""


@dataclass
class MigrationResult:
    migrated: list[str]
    failed: list[str]


def _keyring():
    try:
        import keyring
        return keyring
    except ImportError as e:
        raise SecretStoreError("keyring is not installed") from e


def _validate_key(key: str):
    if key not in SECRET_KEYS:
        raise KeyError(f"Unsupported secret key: {key}")


def get_secret(key: str) -> str | None:
    _validate_key(key)
    if key in _runtime_cache:
        return _runtime_cache[key]
    try:
        value = _keyring().get_password(SERVICE_NAME, key)
    except Exception as e:
        raise SecretStoreError(f"Could not access Keychain for {key}") from e
    if value:
        _runtime_cache[key] = value
    return value


def has_secret(key: str) -> bool:
    return bool(get_secret(key))


def set_secret(key: str, value: str):
    _validate_key(key)
    if not value:
        delete_secret(key)
        return
    try:
        _keyring().set_password(SERVICE_NAME, key, value)
    except Exception as e:
        raise SecretStoreError(f"Could not write {key} to Keychain") from e
    _runtime_cache[key] = value


def delete_secret(key: str):
    _validate_key(key)
    _runtime_cache.pop(key, None)
    try:
        keyring = _keyring()
        try:
            keyring.delete_password(SERVICE_NAME, key)
        except Exception as e:
            if getattr(e, "__class__", type(e)).__name__ != "PasswordDeleteError":
                raise
    except Exception as e:
        raise SecretStoreError(f"Could not delete {key} from Keychain") from e


def migrate_secrets_from_config(cfg: dict) -> MigrationResult:
    """Move any legacy secrets from config JSON into Keychain."""
    migrated: list[str] = []
    failed: list[str] = []
    changed = False

    for key in SECRET_KEYS:
        if key not in cfg:
            continue
        value = cfg.get(key)
        if not value:
            cfg.pop(key, None)
            changed = True
            continue
        try:
            set_secret(key, value)
        except SecretStoreError:
            failed.append(key)
            continue
        cfg.pop(key, None)
        migrated.append(key)
        changed = True

    if changed:
        save_config(cfg)
    if migrated:
        log.info("migrated %d secrets from config to Keychain", len(migrated))
    return MigrationResult(migrated=migrated, failed=failed)
