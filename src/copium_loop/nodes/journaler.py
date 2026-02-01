from copium_loop.constants import DEFAULT_MODELS
from copium_loop.gemini import invoke_gemini
from copium_loop.memory import MemoryManager
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry


async def journaler(state: AgentState) -> dict:
    telemetry = get_telemetry()
    telemetry.log_status("journaler", "active")
    telemetry.log_output("journaler", "--- Journaling Node ---\n")
    print("--- Journaling Node ---")

    test_output = state.get("test_output", "")
    review_status = state.get("review_status", "")
    git_diff = state.get("git_diff", "")
    telemetry_log = telemetry.get_formatted_log()

    # Construct a prompt to distill the session
    prompt = f"""Analyze the following development session and distill it into a single, concise "Lesson Learned" for future sessions.

    CONTEXT:
    You are generating input for a `save_memory` tool. This tool tracks your overall experience as an agent to improve over time.
    Your output will be prefixed with a timestamp and saved to `GEMINI.md`.

    RULES:
    1.  The lesson must be a one-sentence fact or rule that will help you avoid mistakes or follow best practices in this codebase.
    2.  Strictly NO status reports (e.g., "I fixed the bug", "I ran tests").
    3.  Strictly NO summaries of what happened.
    4.  If there is no significant lesson learned (e.g., routine work), return exactly "NO_LESSON".

    SESSION OUTCOME:
    Review Status: {review_status}
    Test Output: {test_output}

    CHANGES MADE (Diff):
    {git_diff}

    TELEMETRY LOG:
    {telemetry_log}

    Provide ONLY the distilled lesson as a single sentence, or "NO_LESSON"."""

    models = [None] + DEFAULT_MODELS
    lesson = await invoke_gemini(
        prompt,
        ["--yolo"],
        models=models,
        verbose=state.get("verbose"),
        label="Journaler System",
        node="journaler",
    )

    lesson = lesson.strip().strip('"').strip("'")

    if lesson.upper() == "NO_LESSON" or not lesson:
        telemetry.log_output("journaler", "\nNo lesson learned.\n")
        print("\nNo lesson learned.")
        telemetry.log_status("journaler", "no_lesson")
        return {"journal_status": "no_lesson"}

    memory_manager = MemoryManager()
    memory_manager.log_learning(lesson)

    telemetry.log_output("journaler", f"\nLesson Learned: {lesson}\n")
    print(f"\nLesson Learned: {lesson}")
    telemetry.log_status("journaler", "journaled")

    return {"journal_status": "journaled"}
