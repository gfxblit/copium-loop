from langchain_core.messages import SystemMessage
from copium_loop.state import AgentState
from copium_loop.constants import REVIEWER_MODELS
from copium_loop.utils import invoke_gemini, notify

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

    review_content = await invoke_gemini(system_prompt, ['--yolo'], models=REVIEWER_MODELS)
    
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
