import os
from langchain_core.messages import SystemMessage
from copium_loop.state import AgentState
from copium_loop.utils import run_command, notify

async def tester(state: AgentState) -> dict:
    print('--- Test Runner Node ---')
    retry_count = state.get('retry_count', 0)

    try:
        # Determine test command
        test_cmd = 'npm'
        test_args = ['test']

        if os.environ.get('COPIUM_TEST_CMD'):
            parts = os.environ.get('COPIUM_TEST_CMD').split()
            test_cmd = parts[0]
            test_args = parts[1:]
        elif os.path.exists('pyproject.toml') or os.path.exists('setup.py') or os.path.exists('requirements.txt'):
             test_cmd = 'pytest'
             test_args = []
        elif os.path.exists('package.json'):
             test_cmd = 'npm'
             test_args = ['test']

        print(f'Running {test_cmd} {" ".join(test_args)}...')
        result = await run_command(test_cmd, test_args)
        unit_output = result['output']
        exit_code = result['exit_code']

        if exit_code != 0 or 'FAIL' in unit_output or 'failed' in unit_output:
            message = 'Max retries exceeded. Aborting.' if retry_count >= 3 else 'Unit tests failed. Returning to coder.'
            await notify('Workflow: Tests Failed', message, 4)
            
            return {
                'test_output': 'FAIL (Unit):\n' + unit_output,
                'retry_count': retry_count + 1,
                'messages': [SystemMessage(content='Tests failed (Unit):\n' + unit_output)],
            }
        
        return {'test_output': 'PASS'}
    except Exception as error:
        return {
            'test_output': 'FAIL: ' + str(error),
            'retry_count': retry_count + 1,
        }
