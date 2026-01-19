import re
import os
from langchain_core.messages import SystemMessage
from copium_loop.state import AgentState
from copium_loop.utils import run_command, notify

async def pr_creator(state: AgentState) -> dict:
    print('--- PR Creator Node ---')
    retry_count = state.get('retry_count', 0)

    if not os.path.exists('.git'):
        print('Not a git repository. Skipping PR creation.')
        return {'review_status': 'pr_skipped'}

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
