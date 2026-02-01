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


def test_get_project_memories(tmp_path):
    manager = MemoryManager(project_root=tmp_path)
    memory_file = tmp_path / "GEMINI.md"
    memory_file.write_text("- [2026-01-31 18:02:11] Fact 1\n- [2026-01-31 18:09:36] Fact 2\n")

    memories = manager.get_project_memories()
    assert memories == ["Fact 1", "Fact 2"]


def test_get_project_memories_empty(tmp_path):
    manager = MemoryManager(project_root=tmp_path)
    assert manager.get_project_memories() == []
