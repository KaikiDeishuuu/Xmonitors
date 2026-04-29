from pathlib import Path
from xmonitors.state import load_state, save_state_atomic


class DummyLogger:
    def error(self, *args, **kwargs):
        pass


def test_state_load_missing(tmp_path):
    state_path = tmp_path / "state.json"
    state = load_state(str(state_path), DummyLogger())
    assert state == {}
    assert state_path.exists()


def test_state_atomic_save(tmp_path):
    state_path = tmp_path / "state.json"
    save_state_atomic(str(state_path), {"item": {"last_status": "IN_STOCK"}})
    assert Path(state_path).exists()
    assert "IN_STOCK" in state_path.read_text(encoding="utf-8")
