from copium_loop.constants import MODELS
from copium_loop.engine.base import LLMEngine
from copium_loop.memory import MemoryManager
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry


async def journaler_node(state: AgentState, engine: LLMEngine) -> dict:
    telemetry = get_telemetry()
    telemetry.log_status("journaler", "active")
    telemetry.log_output("journaler", "--- Journaling Node ---\n")
    print("--- Journaling Node ---")

    try:
        memory_manager = MemoryManager()
        existing_memories = memory_manager.get_project_memories()
        existing_memories_str = "\n    ".join(f"- {m}" for m in existing_memories)

        test_output = state.get("test_output", "")
        review_status = state.get("review_status", "")
        git_diff = state.get("git_diff", "")
        telemetry_log = telemetry.get_formatted_log()

        # Construct a prompt to distill the session
        prompt = f"""Analyze the following development session and distill key learnings.

    DECISION LOGIC:
    1. **Global/Experiential Memory**: If the lesson is about the user's preferences (e.g., "User hates async"), general coding patterns, or your own behavior that applies to ALL projects:
       -> Use the `save_memory` tool to save this fact. Ensure you include a timestamp so you can tell if it's a recent memory or not.
    2. **Project-Specific Memory**: If the lesson is specific to THIS codebase (e.g., "The `foobar` module is deprecated", "Always import X from Y"):
       -> Output the lesson text directly.

    ANTI-PATTERNS (WHAT NOT TO LOG):
    - Do NOT log "changelogs" or "status reports" of what you just did.
    - Do NOT log vague statements like "Updated the code."
    - Do NOT log things that are already obvious from the git history.

    PRINCIPLES:
    - Focus on the *principle* or *rule* that was established or discovered.
    - Make it actionable for future agents.
    - Use the "Bad" vs "Good" examples below as a guide.

    EXAMPLES:
    - Bad: The journaler node now deduplicates learnings.
    - Good: Deduplicate learnings by checking against existing memories before logging.
    - Bad: Added a check for null values in the user object.
    - Good: Always check for null values in the user object before accessing properties to prevent runtime errors.

    RULES:
    - You can do BOTH if applicable.
    - If you strictly used `save_memory` and have no project-specific lesson, output "NO_LESSON".
    - If the project-specific lesson is redundant with existing memories, output "NO_LESSON".
    - If you have a project lesson, output ONLY that single sentence.
    - Strictly NO status reports or summaries.

    EXISTING PROJECT MEMORIES:
    {existing_memories_str if existing_memories_str else "None yet."}

    SESSION OUTCOME:
    Review Status: {review_status}
    Test Output: {test_output}

    CHANGES MADE (Diff):
    {git_diff}

    TELEMETRY LOG:
    {telemetry_log}

    Output ONLY the project lesson or "NO_LESSON"."""

        models = [None] + MODELS
        lesson = await engine.invoke(
            prompt,
            ["--yolo"],
            models=models,
            verbose=state.get("verbose"),
            label="Journaler System",
            node="journaler",
            jules_metadata=state.get("jules_metadata"),
        )

        lesson = lesson.strip().strip('"').strip("'")

        review_status = state.get("review_status", "pending")
        # If we are at the journaler and not planning to go to pr_creator,
        # ensure the review_status reflects that we've finished journaling.
        new_review_status = "journaled" if review_status == "pending" else review_status

        if lesson.upper() == "NO_LESSON" or not lesson:
            telemetry.log_output("journaler", "\nNo lesson learned.\n")
            print("\nNo lesson learned.")
            telemetry.log_status("journaler", "no_lesson")
            return {
                "journal_status": "no_lesson",
                "review_status": new_review_status,
                "jules_metadata": state.get("jules_metadata"),
            }

        memory_manager.log_learning(lesson)

        telemetry.log_output("journaler", f"\nLesson Learned: {lesson}\n")
        print(f"\nLesson Learned: {lesson}")
        telemetry.log_status("journaler", "journaled")

        return {
            "journal_status": "journaled",
            "review_status": new_review_status,
            "jules_metadata": state.get("jules_metadata"),
        }

    except Exception as e:
        error_msg = f"Journaling failed gracefully: {e}"
        telemetry.log_output("journaler", f"\n{error_msg}\n")
        print(f"\n{error_msg}")
        telemetry.log_status("journaler", "failed")

        # Ensure we don't block the loop, proceed as if journaled
        current_status = state.get("review_status", "pending")
        fallback_status = "journaled" if current_status == "pending" else current_status
        return {
            "journal_status": "failed",
            "review_status": fallback_status,
            "jules_metadata": state.get("jules_metadata"),
        }
