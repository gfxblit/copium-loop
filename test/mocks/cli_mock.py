#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path


def main():
    tool_name = Path(sys.argv[0]).name
    instructions_path = os.environ.get("CLI_MOCK_INSTRUCTIONS")

    if "--version" in sys.argv:
        print(f"mock-{tool_name} version 1.0.0")
        sys.exit(0)

    if not instructions_path or not os.path.exists(instructions_path):
        print(
            f"Mock {tool_name} called but CLI_MOCK_INSTRUCTIONS not set or file missing.",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(instructions_path) as f:
        all_instructions = json.load(f)

    tool_instructions = all_instructions.get(tool_name, [])

    # We need to know which call this is.
    # Let's use another file to track the counter for each tool.
    counter_path = Path(instructions_path).with_suffix(".counter")
    if counter_path.exists():
        with open(counter_path) as f:
            counters = json.load(f)
    else:
        counters = {}

    index = counters.get(tool_name, 0)

    if index >= len(tool_instructions):
        print(
            f"Mock {tool_name} called more times than instructions provided (call index {index}).",
            file=sys.stderr,
        )
        sys.exit(1)

    instruction = tool_instructions[index]

    # Increment counter
    counters[tool_name] = index + 1
    with open(counter_path, "w") as f:
        json.dump(counters, f)

    # Process instruction
    stdout = instruction.get("stdout", "")
    stderr = instruction.get("stderr", "")
    exit_code = instruction.get("exit_code", 0)
    write_files = instruction.get("write_files", {})
    shell = instruction.get("shell", "")

    for file_path, content in write_files.items():
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    if shell:
        import subprocess

        subprocess.run(shell, shell=True, check=False)

    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
