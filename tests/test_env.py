from pathlib import Path

from cinescrapper import env


def test_load_project_env_uses_configured_env_file_and_preserves_shell_values(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CINESCRAPPER_TEST_FROM_DOTENV=loaded\n"
        "CINESCRAPPER_TEST_PRECEDENCE=from-file\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(env, "ENV_FILE", env_file)
    monkeypatch.delenv("CINESCRAPPER_TEST_FROM_DOTENV", raising=False)
    monkeypatch.setenv("CINESCRAPPER_TEST_PRECEDENCE", "from-shell")

    returned_path = env.load_project_env()

    assert returned_path == env_file
    assert __import__("os").environ["CINESCRAPPER_TEST_FROM_DOTENV"] == "loaded"
    assert __import__("os").environ["CINESCRAPPER_TEST_PRECEDENCE"] == "from-shell"


def test_mongo_settings_supports_legacy_environment_names(monkeypatch, tmp_path):
    monkeypatch.setattr(env, "ENV_FILE", tmp_path / "missing.env")
    for key in (
        "CINESCRAPPER_MONGO_URI", "MONGODB_URI",
        "CINESCRAPPER_MONGODB_DATABASE", "MONGODB_DATABASE",
        "CINESCRAPPER_MONGODB_COLLECTION", "MONGODB_COLLECTION",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("MONGODB_URI", "mongodb://example:27017")
    monkeypatch.setenv("MONGODB_DATABASE", "test_db")
    monkeypatch.setenv("MONGODB_COLLECTION", "test_collection")

    settings = env.mongo_settings()

    assert settings == {
        "uri": "mongodb://example:27017",
        "database": "test_db",
        "collection": "test_collection",
    }
