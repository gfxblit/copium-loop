"""Core workflow implementation."""

import asyncio
import os
import sys
import subprocess
import re
from typing import TypedDict, Annotated, List, Union, Any, Optional
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

# Default models to try in order
DEFAULT_MODELS = [
    'gemini-3-pro-preview',
    'gemini-3-flash-preview',
    'gemini-2.5-pro',
    'gemini-2.5-flash',
]


class AgentState(TypedDict):
    """The state of the workflow."""
    messages: Annotated[List[BaseMessage], add_messages]
    code_status: str
    test_output: str
    review_status: str
    retry_count: int
    pr_url: str
    issue_url: str


class WorkflowManager:
    """
    Manages the TDD development workflow using LangGraph and Gemini.
    Orchestrates the coding, testing, and review phases.
    """

    def __init__(self, start_node: Optional[str] = None, verbose: bool = False):
        self.graph = None
        self.start_node = start_node
        self.verbose = verbose

    # --- Helpers ---

    def _stream_output(self, chunk: str):
        """Streams a chunk of output to stdout."""
        if not chunk:
            return
        sys.stdout.write(chunk)
        sys.stdout.flush()

    def _clean_chunk(self, chunk: Union[str, bytes]) -> str:
        """
        Cleans a chunk of output by removing null bytes, non-printable control
        characters, and ANSI escape codes.
        """
        if isinstance(chunk, bytes):
            try:
                chunk = chunk.decode('utf-8', errors='replace')
            except Exception:
                return ''
        
        if not isinstance(chunk, str):
            return str(chunk)

        # Remove ANSI escape codes
        without_ansi = re.sub(r'\x1B\[[0-9;]*[a-zA-Z]', '', chunk)

        # Remove disruptive control characters (excluding TAB, LF, CR)
        return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', without_ansi)

    async def run_command(self, command: str, args: List[str] = []) -> dict:
        """
        Invokes a shell command and streams output to stdout.
        Returns the combined stdout/stderr output and exit code.
        """
        process = await asyncio.create_subprocess_exec(
            command, *args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        full_output = ""
        
        async def read_stream(stream, is_stderr):
            nonlocal full_output
            while True:
                line = await stream.read(1024)
                if not line:
                    break
                decoded_chunk = self._clean_chunk(line)
                if decoded_chunk:
                    if not is_stderr:
                        self._stream_output(decoded_chunk)
                    full_output += decoded_chunk

        await asyncio.gather(
            read_stream(process.stdout, False),
            read_stream(process.stderr, True)
        )

        exit_code = await process.wait()
        return {'output': full_output, 'exit_code': exit_code}

    async def _execute_gemini(self, prompt: str, model: str, args: List[str] = []) -> str:
        """Internal method to execute the Gemini CLI with a specific model."""
        cmd_args = ['-m', model] + args + [prompt]
        
        process = await asyncio.create_subprocess_exec(
            'gemini', *cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        full_output = ""
        error_output = ""

        async def read_stdout():
            nonlocal full_output
            while True:
                chunk = await process.stdout.read(1024)
                if not chunk:
                    break
                decoded = self._clean_chunk(chunk)
                if decoded:
                    self._stream_output(decoded)
                    full_output += decoded

        async def read_stderr():
            nonlocal error_output
            while True:
                chunk = await process.stderr.read(1024)
                if not chunk:
                    break
                decoded = self._clean_chunk(chunk)
                if decoded:
                    error_output += decoded

        await asyncio.gather(read_stdout(), read_stderr())
        exit_code = await process.wait()

        if exit_code != 0:
            raise Exception(f"Gemini CLI exited with code {exit_code}: {error_output}")
        
        return full_output.strip()

    async def invoke_gemini(self, prompt: str, args: List[str] = []) -> str:
        """
        Invokes the Gemini CLI with a prompt, supporting model fallback.
        Streams output to stdout and returns the full response.
        """
        for i, model in enumerate(DEFAULT_MODELS):
            try:
                print(f"Using model: {model}")
                return await self._execute_gemini(prompt, model, args)
            except Exception as error:
                error_msg = str(error)
                is_quota_error = 'TerminalQuotaError' in error_msg or '429' in error_msg
                is_last_model = i == len(DEFAULT_MODELS) - 1

                if is_quota_error and not is_last_model:
                    next_model = DEFAULT_MODELS[i + 1]
                    print(f"Quota exhausted for {model}. Falling back to {next_model}...")
                    continue
                
                if is_quota_error and is_last_model:
                    raise Exception(f"All models exhausted. Last error: {error_msg}")
                
                raise error
        return ""

    async def get_tmux_session(self) -> str:
        """Retrieves the current tmux session name."""
        try:
            process = await asyncio.create_subprocess_exec(
                'tmux', 'display-message', '-p', '#S',
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            output = stdout.decode().strip()
            if output:
                return output
        except Exception:
            pass
        return 'no-tmux'

    async def notify(self, title: str, message: str, priority: int = 3):
        """Sends a notification to ntfy.sh if NTFY_CHANNEL is set."""
        channel = os.environ.get('NTFY_CHANNEL')
        if not channel:
            return

        session_name = await self.get_tmux_session()
        full_message = f"Session: {session_name}\n{message}"

        try:
            await self.run_command('curl', [
                '-sS',
                '-H', f"Title: {title}",
                '-H', f"Priority: {priority}",
                '-d', full_message,
                f"https://ntfy.sh/{channel}"
            ])
        except Exception as e:
            print(f"Failed to send notification: {e}")

    # --- Nodes ---

    async def coder(self, state: AgentState) -> dict:
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

        if self.verbose:
            print('\n--- [VERBOSE] Coder System Prompt ---')
            print(system_prompt)
            print('------------------------------------\n')

        code_content = await self.invoke_gemini(system_prompt, ['--yolo'])
        print('\nCoding complete.')

        return {
            'code_status': 'coded',
            'messages': [SystemMessage(content=code_content)],
        }

    async def test_runner(self, state: AgentState) -> dict:
        print('--- Test Runner Node ---')
        retry_count = state.get('retry_count', 0)

        try:
            print('Running npm test...')
            result = await self.run_command('npm', ['test'])
            unit_output = result['output']
            exit_code = result['exit_code']

            if exit_code != 0 or 'FAIL' in unit_output or 'failed' in unit_output:
                message = 'Max retries exceeded. Aborting.' if retry_count >= 3 else 'Unit tests failed. Returning to coder.'
                await self.notify('Workflow: Tests Failed', message, 4)
                
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

    async def reviewer(self, state: AgentState) -> dict:
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

        if self.verbose:
            print('\n--- [VERBOSE] Reviewer System Prompt ---')
            print(system_prompt)
            print('--------------------------------------\n')

        review_content = await self.invoke_gemini(system_prompt, ['--yolo'])
        
        is_approved = "APPROVED" in review_content
        print(f"\nReview decision: {'Approved' if is_approved else 'Rejected'}")

        if not is_approved:
            message = 'Max retries exceeded. Aborting.' if retry_count >= 3 else 'Reviewer rejected the implementation. Returning to coder.'
            await self.notify('Workflow: Review Rejected', message, 4)
        
        return {
            'review_status': 'approved' if is_approved else 'rejected',
            'messages': [SystemMessage(content=review_content)],
            'retry_count': retry_count if is_approved else retry_count + 1,
        }

    async def pr_creator(self, state: AgentState) -> dict:
        print('--- PR Creator Node ---')
        retry_count = state.get('retry_count', 0)

        try:
            # 1. Check feature branch
            res_branch = await self.run_command('git', ['branch', '--show-current'])
            branch_name = res_branch['output'].strip()
            
            if res_branch['exit_code'] != 0 or branch_name in ['main', 'master'] or not branch_name:
                print('Not on a feature branch. Skipping PR creation.')
                return {'review_status': 'pr_skipped'}
            
            print(f"On feature branch: {branch_name}")

            # 2. Check uncommitted changes
            res_status = await self.run_command('git', ['status', '--porcelain'])
            if res_status['output'].strip():
                print('Uncommitted changes found. Returning to coder to finalize commits.')
                message = 'Max retries exceeded. Aborting due to uncommitted changes.' if retry_count >= 3 else 'Uncommitted changes found. Returning to coder.'
                await self.notify('Workflow: Uncommitted Changes', message, 4)
                return {
                    'review_status': 'needs_commit',
                    'messages': [SystemMessage(content='Uncommitted changes found. Please ensure all changes are committed before creating a PR.')],
                    'retry_count': retry_count + 1,
                }
            
            # 3. Push to origin
            print('Pushing to origin...')
            res_push = await self.run_command('git', ['push', '-u', 'origin', branch_name])
            if res_push['exit_code'] != 0:
                raise Exception(f"Git push failed (exit {res_push['exit_code']}): {res_push['output'].strip()}")

            # 4. Create PR
            print('Creating Pull Request...')
            res_pr = await self.run_command('gh', ['pr', 'create', '--fill'])
            
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
            await self.notify('Workflow: PR Failed', message, 5)
            return {
                'review_status': 'pr_failed',
                'messages': [SystemMessage(content=f"Failed to create PR: {error}")],
                'retry_count': retry_count + 1,
            }

    # --- Conditional Logic ---

    def should_continue_from_test(self, state: AgentState) -> str:
        if state.get('test_output') == 'PASS':
            return 'reviewer'
        
        if state.get('retry_count', 0) > 3:
            print('Max retries exceeded. Aborting.')
            return END
        
        return 'coder'

    def should_continue_from_review(self, state: AgentState) -> str:
        if state.get('review_status') == 'approved':
            return 'pr_creator'
        
        if state.get('retry_count', 0) > 3:
            print('Max retries exceeded. Aborting.')
            return END
        
        return 'coder'
    
    def should_continue_from_pr_creator(self, state: AgentState) -> str:
        status = state.get('review_status')
        if status in ['pr_created', 'pr_skipped']:
            return END
        
        if state.get('retry_count', 0) > 3:
            print('Max retries exceeded in PR Creator. Aborting.')
            return END
        
        print(f"PR Creator failed or needs commit (status: {status}). Returning to coder.")
        return 'coder'

    def create_graph(self):
        workflow = StateGraph(AgentState)

        # Add Nodes
        workflow.add_node('coder', self.coder)
        workflow.add_node('test_runner', self.test_runner)
        workflow.add_node('reviewer', self.reviewer)
        workflow.add_node('pr_creator', self.pr_creator)

        # Determine entry point
        valid_nodes = ['coder', 'test_runner', 'reviewer', 'pr_creator']
        entry_node = self.start_node if self.start_node in valid_nodes else 'coder'
        
        if self.start_node and self.start_node not in valid_nodes:
            print(f"Warning: Invalid start node \"{self.start_node}\".")
            print(f"Valid nodes are: {', '.join(valid_nodes)}")
            print('Falling back to "coder".')

        # Edges
        workflow.add_edge(START, entry_node)
        workflow.add_edge('coder', 'test_runner')

        workflow.add_conditional_edges(
            'test_runner',
            self.should_continue_from_test,
            {
                'reviewer': 'reviewer',
                'coder': 'coder',
                END: END
            }
        )

        workflow.add_conditional_edges(
            'reviewer',
            self.should_continue_from_review,
            {
                'pr_creator': 'pr_creator',
                'coder': 'coder',
                END: END
            }
        )

        workflow.add_conditional_edges(
            'pr_creator',
            self.should_continue_from_pr_creator,
            {
                END: END,
                'coder': 'coder'
            }
        )

        self.graph = workflow.compile()
        return self.graph

    async def run(self, input_prompt: str):
        """Run the workflow with the given prompt."""
        issue_match = re.search(r'https://github\.com/[^\s]+/issues/\d+', input_prompt)
        
        if not self.start_node:
            self.start_node = 'coder'
        
        print(f"Starting workflow at node: {self.start_node}")

        if not self.graph:
            self.create_graph()

        initial_state = {
            'messages': [HumanMessage(content=input_prompt)],
            'retry_count': 0,
            'issue_url': issue_match.group(0) if issue_match else '',
            'test_output': '' if self.start_node not in ['reviewer', 'pr_creator'] else '',
            'code_status': 'pending',
            'review_status': 'approved' if self.start_node == 'pr_creator' else 'pending',
            'pr_url': ''
        }
        
        return await self.graph.ainvoke(initial_state)
