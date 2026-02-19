from langchain_core.messages import SystemMessage

from copium_loop.constants import MODELS
from copium_loop.nodes.utils import get_coder_prompt
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry


async def coder_node(state: AgentState) -> dict:
    telemetry = get_telemetry()
    telemetry.log_status("coder", "active")
    telemetry.log_output("coder", "--- Coder Node ---\n")
    print("--- Coder Node ---")

    engine = state["engine"]
    system_prompt = await get_coder_prompt(engine.engine_type, state, engine)

    # Start with "auto" (None), then fallback to default models
    coder_models = [None] + MODELS
    code_content = await engine.invoke(
        system_prompt,
        ["--yolo"],
        models=coder_models,
        verbose=state.get("verbose"),
        label="Coder System",
        node="coder",
    )
    telemetry.log_output("coder", "\nCoding complete.\n")
    print("\nCoding complete.")
    telemetry.log_status("coder", "coded")

    return {
        "code_status": "coded",
        "messages": [SystemMessage(content=code_content)],
    }
