"""Data-directory configuration: override, environment variable, local .env."""

import pytest

from bearingguard.config import DATA_DIR_ENV, get_data_dir, read_dotenv


def test_dotenv_used_when_env_var_unset(tmp_path, monkeypatch):
    monkeypatch.delenv(DATA_DIR_ENV, raising=False)
    env = tmp_path / ".env"
    env.write_text(f"# local\n{DATA_DIR_ENV}='{tmp_path / 'ims'}'\nOTHER=1\n")
    assert read_dotenv(env)["OTHER"] == "1"
    assert get_data_dir(dotenv=env) == (tmp_path / "ims").resolve()


def test_env_var_and_override_take_precedence(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(f"{DATA_DIR_ENV}={tmp_path / 'from_file'}\n")
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path / "from_env"))
    assert get_data_dir(dotenv=env).name == "from_env"
    assert get_data_dir(tmp_path / "explicit", dotenv=env).name == "explicit"


def test_missing_configuration_explains_options(tmp_path, monkeypatch):
    monkeypatch.delenv(DATA_DIR_ENV, raising=False)
    with pytest.raises(RuntimeError, match=".env.example"):
        get_data_dir(dotenv=tmp_path / "absent.env")
