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
