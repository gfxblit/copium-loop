import re
import os
from langchain_core.messages import SystemMessage
from langgraph.graph import END

from copium_loop.state import AgentState
from copium_loop.utils import invoke_gemini, run_command, notify

async def coder(state: AgentState) -> dict:
    print('--- Coder Node ---')
    messages = state['messages']
    test_output = state.get('test_output', '')
    review_status = state.get('review_status', '')
    
    initial_request = messages[0].content
    
    system_prompt = f"""You are a software engineer. Implement the following request: {initial_request}. 
    You have access to the file system and git.

    IMPORTANT: You MUST commit your changes using git. You may create multiple commits if it makes sense for the task.
    Please output the code changes in markdown blocks as well for the conversation record."""

    if test_output and ('FAIL' in test_output or 'failed' in test_output):
        system_prompt = f"""Your previous implementation failed tests. 
    
    TEST OUTPUT:
    {test_output}
    
    Please fix the code to satisfy the tests and the original request: {initial_request}."""
        system_prompt += '\n\nMake sure to commit your fixes.'
    elif review_status == 'rejected':
        last_message = messages[-1]
        system_prompt = f"""Your previous implementation was rejected by the reviewer. 
    
    REVIEWER FEEDBACK:
    {last_message.content}
    
    Please fix the code to satisfy the reviewer and the original request: {initial_request}."""
        system_prompt += '\n\nMake sure to commit your fixes.'
    elif review_status == 'needs_commit':
        system_prompt = f"""You have uncommitted changes that prevent PR creation. 
    Please review your changes and commit them using git.
    Original request: {initial_request}"""

    if state.get('verbose'):
        print('\n--- [VERBOSE] Coder System Prompt ---')
        print(system_prompt)
        print('------------------------------------\n')

    code_content = await invoke_gemini(system_prompt, ['--yolo'])
    print('\nCoding complete.')

    return {
        'code_status': 'coded',
        'messages': [SystemMessage(content=code_content)],
    }

async def run_tests(state: AgentState) -> dict:
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

async def reviewer(state: AgentState) -> dict:
    print('--- Reviewer Node ---')
    test_output = state.get('test_output', '')
    retry_count = state.get('retry_count', 0)

    if test_output and 'PASS' not in test_output:
        return {
            'review_status': 'rejected',
            'messages': [SystemMessage(content='Tests failed.')],
            'retry_count': retry_count + 1,
        }
    
    system_prompt = """You are a senior reviewer. Review the implementation. 
    You have access to the file system and git.

    MANDATORY: You MUST activate the 'pr-reviewer' skill to perform a thorough review of the changes. 

    You MUST examine all commits and the full diff between the current branch and 'origin/main'.
    Use tools like 'git log origin/main..HEAD' to see the commit history and 'git diff origin/main..HEAD' to review the code changes.

    You MUST evaluate commit granularity. Reject the implementation if:
    1. Commits are too large: They bundle multiple unrelated tasks or ideas, making them difficult to review (cognitive overload).
    2. Commits are too small: There are too many tiny, fragmented commits that lack independent value and should have been grouped or squashed.

    If the code looks correct, safe, and follows the requirements, output "APPROVED". 
    Otherwise, output "REJECTED" followed by a concise explanation of why."""

    if state.get('verbose'):
        print('\n--- [VERBOSE] Reviewer System Prompt ---')
        print(system_prompt)
        print('--------------------------------------\n')

    review_content = await invoke_gemini(system_prompt, ['--yolo'])
    
    is_approved = "APPROVED" in review_content
    print(f"\nReview decision: {'Approved' if is_approved else 'Rejected'}")

    if not is_approved:
        message = 'Max retries exceeded. Aborting.' if retry_count >= 3 else 'Reviewer rejected the implementation. Returning to coder.'
        await notify('Workflow: Review Rejected', message, 4)
    
    return {
        'review_status': 'approved' if is_approved else 'rejected',
        'messages': [SystemMessage(content=review_content)],
        'retry_count': retry_count if is_approved else retry_count + 1,
    }

async def pr_creator(state: AgentState) -> dict:
    print('--- PR Creator Node ---')
    retry_count = state.get('retry_count', 0)

    try:
        # 1. Check feature branch
        res_branch = await run_command('git', ['branch', '--show-current'])
        branch_name = res_branch['output'].strip()
        
        if res_branch['exit_code'] != 0 or branch_name in ['main', 'master'] or not branch_name:
            print('Not on a feature branch. Skipping PR creation.')
            return {'review_status': 'pr_skipped'}
        
        print(f"On feature branch: {branch_name}")

        # 2. Check uncommitted changes
        res_status = await run_command('git', ['status', '--porcelain'])
        if res_status['output'].strip():
            print('Uncommitted changes found. Returning to coder to finalize commits.')
            message = 'Max retries exceeded. Aborting due to uncommitted changes.' if retry_count >= 3 else 'Uncommitted changes found. Returning to coder.'
            await notify('Workflow: Uncommitted Changes', message, 4)
            return {
                'review_status': 'needs_commit',
                'messages': [SystemMessage(content='Uncommitted changes found. Please ensure all changes are committed before creating a PR.')],
                'retry_count': retry_count + 1,
            }
        
        # 3. Push to origin
        print('Pushing to origin...')
        res_push = await run_command('git', ['push', '-u', 'origin', branch_name])
        if res_push['exit_code'] != 0:
            raise Exception(f"Git push failed (exit {res_push['exit_code']}): {res_push['output'].strip()}")

        # 4. Create PR
        print('Creating Pull Request...')
        res_pr = await run_command('gh', ['pr', 'create', '--fill'])
        
        if res_pr['exit_code'] != 0:
            if 'already exists' in res_pr['output']:
                print('PR already exists. Treating as success.')
                match = re.search(r'https://github\.com/[^\s]+', res_pr['output'])
                pr_url = match.group(0) if match else 'existing PR'
                return {
                    'review_status': 'pr_created',
                    'pr_url': pr_url,
                    'messages': [SystemMessage(content=f'PR already exists: {pr_url}')]
                }
            raise Exception(f"PR creation failed (exit {res_pr['exit_code']}): {res_pr['output'].strip()}")
        
        pr_output_clean = res_pr['output'].strip()
        print(f"PR created: {pr_output_clean}")
        
        return {
            'review_status': 'pr_created',
            'pr_url': pr_output_clean,
            'messages': [SystemMessage(content=f'PR Created: {pr_output_clean}')]
        }

    except Exception as error:
        print(f"Error in PR creation: {error}")
        message = 'Max retries exceeded. Aborting.' if retry_count >= 3 else f"Failed to create PR: {error}"
        await notify('Workflow: PR Failed', message, 5)
        return {
            'review_status': 'pr_failed',
            'messages': [SystemMessage(content=f"Failed to create PR: {error}")],
            'retry_count': retry_count + 1,
        }

def should_continue_from_test(state: AgentState) -> str:
    if state.get('test_output') == 'PASS':
        return 'reviewer'
    
    if state.get('retry_count', 0) > 3:
        print('Max retries exceeded. Aborting.')
        return END
    
    return 'coder'

def should_continue_from_review(state: AgentState) -> str:
    if state.get('review_status') == 'approved':
        return 'pr_creator'
    
    if state.get('retry_count', 0) > 3:
        print('Max retries exceeded. Aborting.')
        return END
    
    return 'coder'

def should_continue_from_pr_creator(state: AgentState) -> str:
    status = state.get('review_status')
    if status in ['pr_created', 'pr_skipped']:
        return END
    
    if state.get('retry_count', 0) > 3:
        print('Max retries exceeded in PR Creator. Aborting.')
        return END
    
    print(f"PR Creator failed or needs commit (status: {status}). Returning to coder.")
    return 'coder'
