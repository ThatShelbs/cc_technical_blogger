from inferno_ghostwriter.legacy import (
    adopt_legacy_env,
    copy_legacy_secrets,
    move_legacy_app_folder,
    move_legacy_database,
)
from inferno_ghostwriter.secrets import ANTHROPIC_API_KEY, MemorySecretStore


def test_database_is_renamed_with_wal_files(tmp_path):
    (tmp_path / "proseferno.db").write_text("db")
    (tmp_path / "proseferno.db-wal").write_text("wal")
    move_legacy_database(tmp_path / "inferno_ghostwriter.db")
    assert (tmp_path / "inferno_ghostwriter.db").read_text() == "db"
    assert (tmp_path / "inferno_ghostwriter.db-wal").read_text() == "wal"
    assert not (tmp_path / "proseferno.db").exists()


def test_existing_new_database_is_never_replaced(tmp_path):
    (tmp_path / "proseferno.db").write_text("old")
    (tmp_path / "inferno_ghostwriter.db").write_text("new")
    move_legacy_database(tmp_path / "inferno_ghostwriter.db")
    assert (tmp_path / "inferno_ghostwriter.db").read_text() == "new"
    assert (tmp_path / "proseferno.db").exists()


def test_app_folder_moves(tmp_path):
    (tmp_path / "Proseferno" / "data").mkdir(parents=True)
    move_legacy_app_folder(tmp_path / "Inferno Ghostwriter")
    assert (tmp_path / "Inferno Ghostwriter" / "data").is_dir()


def test_secret_is_copied_and_old_one_kept():
    old = MemorySecretStore({ANTHROPIC_API_KEY: "sk-old"})
    new = MemorySecretStore()
    copy_legacy_secrets(new, old)
    assert new.get(ANTHROPIC_API_KEY) == "sk-old"
    assert old.get(ANTHROPIC_API_KEY) == "sk-old"


def test_existing_new_secret_wins():
    old = MemorySecretStore({ANTHROPIC_API_KEY: "sk-old"})
    new = MemorySecretStore({ANTHROPIC_API_KEY: "sk-new"})
    copy_legacy_secrets(new, old)
    assert new.get(ANTHROPIC_API_KEY) == "sk-new"


def test_legacy_env_vars_are_honored_but_do_not_override():
    env = {"PROSEFERNO_PORT": "9000", "PROSEFERNO_MODEL": "a", "INFERNO_GHOSTWRITER_MODEL": "b"}
    adopt_legacy_env(env)
    assert env["INFERNO_GHOSTWRITER_PORT"] == "9000"
    assert env["INFERNO_GHOSTWRITER_MODEL"] == "b"
