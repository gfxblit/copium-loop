"""CLI entry point for copium-loop."""

import argparse
import asyncio
import os
import sys

from copium_loop.copium_loop import WorkflowManager
from copium_loop.telemetry import get_telemetry
from copium_loop.ui import Dashboard


async def async_main():
    """Main async function."""
    parser = argparse.ArgumentParser(description="Run the dev workflow.")
    parser.add_argument("prompt", nargs="*", help="The prompt to run.")
    parser.add_argument(
        "--start",
        "-s",
        type=str,
        help="Start node (coder, test_runner, reviewer, pr_creator)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", default=True, help="Verbose output")
    parser.add_argument("--monitor", "-m", action="store_true", help="Start the Matrix visualization monitor")
    parser.add_argument("--session", type=str, help="Specific session ID to monitor")

    args = parser.parse_args()

    if args.monitor:
        dashboard = Dashboard()
        try:
            dashboard.run_monitor(args.session)
        except KeyboardInterrupt:
            sys.exit(0)
        return

    if not os.environ.get("NTFY_CHANNEL"):
        print("Error: NTFY_CHANNEL environment variable is not defined.")

    prompt = (
        " ".join(args.prompt)
        if args.prompt
        else "Continue development and verify implementation."
    )

    workflow = WorkflowManager(start_node=args.start, verbose=args.verbose)

    try:
        result = await workflow.run(prompt)

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
        else:
            msg = "Workflow failed to converge."
            print(msg, file=sys.stderr)
            await workflow.notify("Workflow: Failed", msg, 5)
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
