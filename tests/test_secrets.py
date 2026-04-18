from __future__ import annotations

import aiquotabar.secrets as secrets


class FakePasswordDeleteError(Exception):
    pass


class FakeKeyring:
    class errors:
        PasswordDeleteError = FakePasswordDeleteError

    def __init__(self):
        self.store = {}
        self.fail_on_set = set()

    def get_password(self, service, key):
        return self.store.get((service, key))

    def set_password(self, service, key, value):
        if key in self.fail_on_set:
            raise RuntimeError("write failed")
        self.store[(service, key)] = value

    def delete_password(self, service, key):
        if (service, key) not in self.store:
            raise FakePasswordDeleteError("missing")
        del self.store[(service, key)]


def test_set_get_has_and_delete_secret(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setattr(secrets, "_keyring", lambda: fake)

    secrets.set_secret("openai_key", "sk-test")

    assert secrets.has_secret("openai_key") is True
    assert secrets.get_secret("openai_key") == "sk-test"

    secrets.delete_secret("openai_key")

    assert secrets.get_secret("openai_key") is None


def test_get_secret_uses_runtime_cache(monkeypatch):
    fake = FakeKeyring()
    fake.store[(secrets.SERVICE_NAME, "openai_key")] = "cached-value"
    monkeypatch.setattr(secrets, "_keyring", lambda: fake)

    assert secrets.get_secret("openai_key") == "cached-value"
    fake.store[(secrets.SERVICE_NAME, "openai_key")] = "new-value"
    assert secrets.get_secret("openai_key") == "cached-value"


def test_unsupported_secret_key_raises():
    try:
        secrets.get_secret("not_supported")
    except KeyError as exc:
        assert "Unsupported secret key" in str(exc)
    else:
        raise AssertionError("Expected KeyError for unsupported secret key")


def test_migrate_secrets_from_config_moves_values_and_cleans_blank_entries(monkeypatch):
    fake = FakeKeyring()
    saved_cfgs = []
    monkeypatch.setattr(secrets, "_keyring", lambda: fake)
    monkeypatch.setattr(secrets, "save_config", lambda cfg: saved_cfgs.append(dict(cfg)))

    cfg = {"openai_key": "sk-live", "cookie_str": "", "refresh": 300}
    result = secrets.migrate_secrets_from_config(cfg)

    assert result.migrated == ["openai_key"]
    assert result.failed == []
    assert "openai_key" not in cfg
    assert "cookie_str" not in cfg
    assert fake.store[(secrets.SERVICE_NAME, "openai_key")] == "sk-live"
    assert saved_cfgs and saved_cfgs[-1]["refresh"] == 300


def test_migrate_secrets_from_config_keeps_failed_keys(monkeypatch):
    fake = FakeKeyring()
    fake.fail_on_set.add("glm_key")
    saved_cfgs = []
    monkeypatch.setattr(secrets, "_keyring", lambda: fake)
    monkeypatch.setattr(secrets, "save_config", lambda cfg: saved_cfgs.append(dict(cfg)))

    cfg = {"glm_key": "bad", "openai_key": "good"}
    result = secrets.migrate_secrets_from_config(cfg)

    assert "openai_key" in result.migrated
    assert "glm_key" in result.failed
    assert "openai_key" not in cfg
    assert cfg["glm_key"] == "bad"
    assert saved_cfgs
