from langchain_core.messages import SystemMessage

from copium_loop.constants import MODELS
from copium_loop.nodes.utils import get_coder_prompt, node_header
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry


@node_header("coder", status_key="code_status", error_value="failed")
async def coder_node(state: AgentState) -> dict:
    telemetry = get_telemetry()

    engine = state["engine"]
    system_prompt = await get_coder_prompt(engine.engine_type, state, engine)

    code_content = await engine.invoke(
        system_prompt,
        ["--yolo"],
        models=MODELS,
        verbose=state.get("verbose"),
        label="Coder System",
        node="coder",
    )
    telemetry.log_info("coder", "\nCoding complete.\n")
    print("\nCoding complete.")
    telemetry.log_status("coder", "coded")

    return {
        "code_status": "coded",
        "messages": [SystemMessage(content=code_content)],
    }
