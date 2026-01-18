"""CLI entry point for copium-loop."""

import asyncio
import os
import sys
import argparse
from copium_loop.workflow import WorkflowManager


async def async_main():
    """Main async function."""
    if not os.environ.get('NTFY_CHANNEL'):
        print('Error: NTFY_CHANNEL environment variable is not defined.')
        print('This is required for workflow notifications. Please set it in your environment or .env file.')
        sys.exit(1)

    parser = argparse.ArgumentParser(description='Run the dev workflow.')
    parser.add_argument('prompt', nargs='*', help='The prompt to run.')
    parser.add_argument('--start', '-s', type=str, help='Start node (coder, test_runner, reviewer, pr_creator)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()

    prompt = ' '.join(args.prompt) if args.prompt else 'Continue development and verify implementation.'
    
    workflow = WorkflowManager(start_node=args.start, verbose=args.verbose)
    
    try:
        result = await workflow.run(prompt)
        
        status = result.get('review_status')
        test_out = result.get('test_output', '')
        pr_url = result.get('pr_url')

        if status == 'pr_created':
            msg = f"Workflow completed successfully. PR created: {pr_url or 'N/A'}"
            print(msg)
            await workflow.notify('Workflow: Success', msg, 3)
            sys.exit(0)
        elif status == 'pr_skipped':
            msg = "Workflow completed successfully. PR skipped (not on a feature branch)."
            print(msg)
            await workflow.notify('Workflow: Success', msg, 3)
            sys.exit(0)
        elif status == 'pr_failed':
            msg = "Workflow completed code/tests but failed to create PR."
            print(msg, file=sys.stderr)
            await workflow.notify('Workflow: PR Failed', msg, 5)
            sys.exit(1)
        elif status == 'approved' and ('PASS' in test_out or not test_out):
            msg = "Workflow completed successfully (no PR)."
            print(msg)
            await workflow.notify('Workflow: Success', msg, 3)
            sys.exit(0)
        else:
            msg = "Workflow failed to converge."
            print(msg, file=sys.stderr)
            await workflow.notify('Workflow: Failed', msg, 5)
            sys.exit(1)

    except Exception as err:
        print(f"Workflow failed: {err}", file=sys.stderr)
        await workflow.notify('Workflow: Error', f"Workflow failed with error: {str(err)}", 5)
        sys.exit(1)


def main():
    """Entry point for the CLI."""
    asyncio.run(async_main())


if __name__ == '__main__':
    main()
