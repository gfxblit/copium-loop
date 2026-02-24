"""CLI entry point for copium-loop."""

import argparse
import asyncio
import os
import sys


async def async_main():
    """Main async function."""
    parser = argparse.ArgumentParser(description="Run the dev workflow.")
    parser.add_argument("prompt", nargs="*", help="The prompt to run.")
    parser.add_argument(
        "-n",
        "--node",
        help="Start node (coder, tester, architect, reviewer, pr_pre_checker, pr_creator, journaler)",
        default=None,
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", default=True, help="Verbose output"
    )
    parser.add_argument(
        "--monitor",
        "-m",
        action="store_true",
        help="Start the Textual-based TUI monitor",
    )
    parser.add_argument(
        "--continue",
        "-c",
        dest="continue_session",
        action="store_true",
        help="Continue from the last incomplete workflow session. If a prompt is provided, it overrides the session prompt.",
    )
    parser.add_argument(
        "--engine",
        type=str,
        choices=["gemini", "jules"],
        default=None,
        help="The LLM engine to use (default: gemini)",
    )

    args = parser.parse_args()

    if args.monitor:
        from copium_loop.ui import TextualDashboard

        app = TextualDashboard()
        await app.run_async()
        return

    from copium_loop.copium_loop import WorkflowManager
    from copium_loop.session_manager import SessionManager
    from copium_loop.telemetry import (
        get_telemetry,
    )

    if not os.environ.get("NTFY_CHANNEL"):
        print("Error: NTFY_CHANNEL environment variable is not defined.")

    # Get derived session ID
    telemetry = get_telemetry()
    session_id = telemetry.session_id
    session_manager = SessionManager(session_id)

    # Determine if we should continue
    # Implicit continue if no prompt provided and session exists (has original prompt or agent state)
    is_resuming = args.continue_session
    prompt_provided = bool(args.prompt)

    if (
        not is_resuming
        and not prompt_provided
        and (session_manager.get_agent_state() or session_manager.get_original_prompt())
    ):
        print(f"Existing session found for this branch: {session_id}")
        print("No prompt provided, implicitly resuming...")
        is_resuming = True

    # Handle resumption logic
    start_node = args.node
    reconstructed_state = None

    if is_resuming:
        print(f"Attempting to continue session: {session_id}")

        # Verify sticky environment (branch and repo root)
        stored_branch = (
            session_manager.get_branch_name() or session_manager.get_metadata("branch")
        )
        stored_repo_root = (
            session_manager.get_repo_root() or session_manager.get_metadata("repo_root")
        )

        from copium_loop.git import get_current_branch
        from copium_loop.shell import run_command

        current_branch = await get_current_branch(node=start_node)
        res = await run_command(
            "git", ["rev-parse", "--show-toplevel"], node=start_node
        )
        current_repo_root = res["output"].strip() if res["exit_code"] == 0 else None

        if stored_branch and stored_branch != current_branch:
            print(
                f"Error: Session branch mismatch. Session: {stored_branch}, Current: {current_branch}"
            )
            sys.exit(1)

        if stored_repo_root and stored_repo_root != current_repo_root:
            print(
                f"Error: Session repo root mismatch. Session: {stored_repo_root}, Current: {current_repo_root}"
            )
            sys.exit(1)

        # Load persisted AgentState
        reconstructed_state = session_manager.get_resumed_state()

        if not reconstructed_state:
            # Fallback to telemetry reconstruction if AgentState is missing (legacy)
            print(
                "Warning: No persisted AgentState found, falling back to telemetry..."
            )
            reconstructed_state = telemetry.reconstruct_state(reset_retries=True)

        # Determine where to resume from
        resume_node, metadata = telemetry.get_last_incomplete_node()

        if resume_node is None:
            reason = metadata.get("reason")
            if reason == "workflow_completed":
                if args.node:
                    print(
                        f"Workflow already completed, but explicit node '{args.node}' provided. Continuing..."
                    )
                    resume_node = args.node
                else:
                    status = metadata.get("status")
                    print(f"Workflow already completed with status: {status}")
                    print("Nothing to continue.")
                    sys.exit(0)
            elif reason == "no_log_found":
                print(f"Error: No log file found for session {session_id}")
                sys.exit(1)
            else:
                print(f"Cannot determine resume point: {reason}")
                sys.exit(1)

        if args.node:
            print(f"Using explicitly provided node: {args.node}")
            start_node = args.node
        else:
            print(f"Resuming from node: {resume_node}")
            start_node = resume_node

        # If prompt is provided via CLI, override the stored prompt
        if args.prompt:
            prompt = " ".join(args.prompt)
            print(f"Overriding session prompt with: {prompt}")
        else:
            # If we have a prompt from the logs/state, use it
            prompt = session_manager.get_original_prompt()
            if prompt is None:
                prompt = reconstructed_state.get(
                    "prompt", "Continue development and verify implementation."
                )

        # Use reconstructed engine if not explicitly provided
        if args.engine is None:
            args.engine = (
                session_manager.get_engine_name()
                or session_manager.get_metadata("engine_name")
            )
            if args.engine is None and "engine_name" in reconstructed_state:
                args.engine = reconstructed_state["engine_name"]
    else:
        prompt = (
            " ".join(args.prompt)
            if args.prompt
            else "Continue development and verify implementation."
        )
        # Store initial prompt in state for persistence
        if reconstructed_state is None:
            reconstructed_state = {}
        reconstructed_state["prompt"] = prompt

    if start_node is None:
        start_node = "coder"

    workflow = WorkflowManager(
        start_node=start_node,
        verbose=args.verbose,
        engine_name=args.engine,
        session_id=session_id,
    )

    try:
        result = await workflow.run(prompt, initial_state=reconstructed_state)

        status = result.get("review_status")
        test_out = result.get("test_output", "")
        pr_url = result.get("pr_url")

        if status == "pr_created":
            msg = f"Workflow completed successfully. PR created: {pr_url or 'N/A'}"
            print(msg)
            get_telemetry().log_workflow_status("success")
            await workflow.notify("Workflow: Success", msg, 3)
            sys.exit(0)
        elif status == "pr_skipped":
            msg = (
                "Workflow completed successfully. PR skipped (not on a feature branch)."
            )
            print(msg)
            get_telemetry().log_workflow_status("success")
            await workflow.notify("Workflow: Success", msg, 3)
            sys.exit(0)
        elif status == "pr_failed":
            msg = "Workflow completed code/tests but failed to create PR."
            print(msg, file=sys.stderr)
            get_telemetry().log_workflow_status("failed")
            await workflow.notify("Workflow: PR Failed", msg, 5)
            sys.exit(1)
        elif status == "approved" and ("PASS" in test_out or not test_out):
            msg = "Workflow completed successfully (no PR)."
            print(msg)
            get_telemetry().log_workflow_status("success")
            await workflow.notify("Workflow: Success", msg, 3)
            sys.exit(0)
        elif status == "journaled":
            if "FAIL" in test_out:
                msg = "Workflow finished with test failures."
                print(msg, file=sys.stderr)
                get_telemetry().log_workflow_status("failed")
                await workflow.notify("Workflow: Failed", msg, 5)
                sys.exit(1)
            msg = "Workflow completed successfully."
            print(msg)
            get_telemetry().log_workflow_status("success")
            await workflow.notify("Workflow: Success", msg, 3)
            sys.exit(0)
        else:
            msg = "Workflow failed to converge."
            print(msg, file=sys.stderr)
            get_telemetry().log_workflow_status("failed")
            await workflow.notify("Workflow: Failed", msg, 5)
            sys.exit(1)

    except ValueError as err:
        print(f"Error: {err}", file=sys.stderr)
        get_telemetry().log_workflow_status("failed")
        sys.exit(1)

    except Exception as err:
        print(f"Workflow failed: {err}", file=sys.stderr)
        get_telemetry().log_workflow_status("failed")
        await workflow.notify(
            "Workflow: Error", f"Workflow failed with error: {str(err)}", 5
        )
        sys.exit(1)


def main():
    """Entry point for the CLI."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
