from copium_loop.memory import MemoryManager


def test_log_learning(tmp_path):
    # Use a temporary directory as the project root
    manager = MemoryManager(project_root=tmp_path)
    fact = "Always check for null pointers."
    manager.log_learning(fact)

    memory_file = tmp_path / "GEMINI.md"
    assert memory_file.exists()
    content = memory_file.read_text()
    assert fact in content
    assert "[20" in content # Basic check for a year in timestamp

def test_get_project_context(tmp_path):
    manager = MemoryManager(project_root=tmp_path)
    memory_file = tmp_path / "GEMINI.md"
    memory_file.write_text("# Project Memory\n\n- [2026-01-31] Use fast tests.")

    context = manager.get_project_context()

    assert "Use fast tests." in context

def test_get_global_memory(tmp_path, monkeypatch):
    # Mock HOME directory
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    gemini_dir = fake_home / ".gemini"
    gemini_dir.mkdir()
    global_memory_file = gemini_dir / "GEMINI.md"
    global_memory_file.write_text("# Global Memory\n\n- Be efficient.")

    manager = MemoryManager(project_root=tmp_path)
    global_context = manager.get_global_context()

    assert "Be efficient." in global_context

def test_get_all_memories(tmp_path, monkeypatch):
    # Mock HOME directory
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    gemini_dir = fake_home / ".gemini"
    gemini_dir.mkdir()
    (gemini_dir / "GEMINI.md").write_text("# Global Memory\n\n- Be efficient.")

    (tmp_path / "GEMINI.md").write_text("# Project Memory\n\n- Use fast tests.")

    manager = MemoryManager(project_root=tmp_path)
    all_context = manager.get_all_memories()

    assert "Be efficient." in all_context
    assert "Use fast tests." in all_context
