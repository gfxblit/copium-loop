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
        "-s",
        "--start",
        help="Start node (coder, tester, architect, reviewer, pr_pre_checker, pr_creator, journaler)",
        default="coder",
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
        "--session", type=str, help="Specific session ID to monitor or continue"
    )
    parser.add_argument(
        "--continue",
        "-c",
        dest="continue_session",
        action="store_true",
        help="Continue from the last incomplete workflow session",
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
    from copium_loop.telemetry import (
        Telemetry,
        find_latest_session,
        get_telemetry,
    )

    if not os.environ.get("NTFY_CHANNEL"):
        print("Error: NTFY_CHANNEL environment variable is not defined.")

    # Handle --continue flag
    start_node = args.start
    reconstructed_state = None

    if args.continue_session:
        # Determine which session to continue
        session_id = args.session
        if not session_id:
            # Try to find the latest session
            session_id = find_latest_session()
            if not session_id:
                print("Error: No previous sessions found to continue.")
                sys.exit(1)

        print(f"Attempting to continue session: {session_id}")

        # Load the telemetry for this session
        telemetry = Telemetry(session_id)

        # Determine where to resume from
        resume_node, metadata = telemetry.get_last_incomplete_node()

        if resume_node is None:
            reason = metadata.get("reason")
            if reason == "workflow_completed":
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

        print(f"Resuming from node: {resume_node}")
        print(f"Metadata: {metadata}")

        # Reconstruct state from logs
        reconstructed_state = telemetry.reconstruct_state()
        start_node = resume_node

        # If we have a prompt from the logs, use it; otherwise use default
        prompt = reconstructed_state.get(
            "prompt", "Continue development and verify implementation."
        )

        # Use reconstructed engine if not explicitly provided
        if args.engine is None and "engine_name" in reconstructed_state:
            args.engine = reconstructed_state["engine_name"]
    else:
        prompt = (
            " ".join(args.prompt)
            if args.prompt
            else "Continue development and verify implementation."
        )

    workflow = WorkflowManager(
        start_node=start_node, verbose=args.verbose, engine_name=args.engine
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
            await workflow.notify("Workflow: Failed", msg, 5)
            sys.exit(1)

    except ValueError as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)

    except Exception as err:
        print(f"Workflow failed: {err}", file=sys.stderr)
        await workflow.notify(
            "Workflow: Error", f"Workflow failed with error: {str(err)}", 5
        )
        sys.exit(1)


def main():
    """Entry point for the CLI."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
