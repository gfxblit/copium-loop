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

    # Construct a prompt to distill the session
    prompt = f"""Analyze the following development session and distill it into a single, concise "Lesson Learned" for future sessions.
    The lesson should be a one-sentence fact or rule that will help you avoid mistakes or follow best practices in this codebase.

    SESSION OUTCOME:
    Review Status: {review_status}
    Test Output: {test_output}

    CHANGES MADE (Diff):
    {git_diff}

    Provide ONLY the distilled lesson as a single sentence."""

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

    memory_manager = MemoryManager()
    memory_manager.log_learning(lesson)

    telemetry.log_output("journaler", f"\nLesson Learned: {lesson}\n")
    print(f"\nLesson Learned: {lesson}")
    telemetry.log_status("journaler", "journaled")

    return {"journal_status": "journaled"}
