import pathlib


def test_readme_contains_architecture_and_flows():
    readme_path = pathlib.Path("README.md")
    assert readme_path.exists(), "README.md not found"

    content = readme_path.read_text()

    # Check for sections
    assert "## Architecture" in content, "README.md missing '## Architecture' section"
    assert "## Flows" in content, "README.md missing '## Flows' section"

    # Check for Architecture components
    assert "LangGraph" in content, "Architecture section should mention LangGraph"
    assert "Gemini" in content or "Jules" in content, "Architecture section should mention LLM engine (Gemini/Jules)"
    assert "Textual" in content, "Architecture section should mention Textual UI"

    # Check for Flow components
    assert "Coder" in content, "Flows section should mention Coder"
    assert "Tester" in content, "Flows section should mention Tester"
    assert "Architect" in content, "Flows section should mention Architect"
    assert "Reviewer" in content, "Flows section should mention Reviewer"
    assert "PR Creator" in content, "Flows section should mention PR Creator"
