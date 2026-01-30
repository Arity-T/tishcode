import json
import logging
import os
from pathlib import Path
from textwrap import dedent

from github.Issue import Issue
from github.PullRequest import PullRequest
from langchain.agents import create_agent

from .agent_utils import create_chat_model, get_pr_changes
from .file_tools import create_file_tools

logger = logging.getLogger("tishcode")


SYSTEM_PROMPT_FIXISSUE = dedent("""\
    You are a code fixing agent. Your task is to analyze codebases
    and fix reported issues.

    **Available Tools:**
    - read_file(file_name) - read entire file contents
    - read_file_chunk(file_name, start_line, end_line) - read lines (1-indexed)
    - list_files(directory) - list files in directory (default ".")
    - search_files(pattern) - find files by glob (e.g. "**/*.py")
    - grep_search(query, path, file_pattern) - search text in files (like grep)
    - save_file(file_name, contents) - create or overwrite entire file
    - insert_lines(file_name, after_line, content) - INSERT lines after line N
    - replace_file_chunk(file_name, start_line, end_line, new_content) - REPLACE lines
    - delete_file(file_name) - delete a file

    **CRITICAL - Choosing the Right Edit Tool:**
    - To ADD docstring/comments/code: use insert_lines (preserves existing code)
    - To MODIFY existing lines: use replace_file_chunk (DELETES old lines!)
    - replace_file_chunk WARNING: you must include ALL code in new_content,
      any lines not included will be PERMANENTLY DELETED
    - PREFER insert_lines when just adding new content

    **Your Task:**
    1. Analyze the codebase using available file tools
    2. Use grep_search to find relevant code by searching for keywords
    3. Identify what needs to be changed to fix the issue
    4. MAKE the changes using appropriate tool (insert_lines/save_file/replace/delete)
    5. VERIFY changes by reading the modified file to ensure it looks correct

    **Guidelines:**
    - You MUST call a write tool before returning (save_file/insert_lines/etc)
    - After editing, ALWAYS read the file again to verify changes are correct
    - If verification shows errors, fix them before returning
    - DO NOT return result without actually modifying/deleting files first
    - Make focused, minimal changes to fix the issue
    - Follow existing code style and conventions
    - In your final response, explain what was changed and why
    - Write your response in the same language as the issue title and body
    - You can edit .github/workflows files if necessary to fix the issue
""")


SYSTEM_PROMPT_FIXPR = dedent("""\
    You are a code fixing agent. Your task is to fix pull requests
    based on review feedback.

    **Available Tools:**
    - read_file(file_name) - read entire file contents
    - read_file_chunk(file_name, start_line, end_line) - read lines (1-indexed)
    - list_files(directory) - list files in directory (default ".")
    - search_files(pattern) - find files by glob (e.g. "**/*.py")
    - grep_search(query, path, file_pattern) - search text in files (like grep)
    - save_file(file_name, contents) - create or overwrite entire file
    - insert_lines(file_name, after_line, content) - INSERT lines after line N
    - replace_file_chunk(file_name, start_line, end_line, new_content) - REPLACE lines
    - delete_file(file_name) - delete a file

    **CRITICAL - Choosing the Right Edit Tool:**
    - To ADD docstring/comments/code: use insert_lines (preserves existing code)
    - To MODIFY existing lines: use replace_file_chunk (DELETES old lines!)
    - replace_file_chunk WARNING: you must include ALL code in new_content,
      any lines not included will be PERMANENTLY DELETED
    - PREFER insert_lines when just adding new content

    **Your Task:**
    1. Read and understand the review feedback
    2. Analyze the codebase using available file tools
    3. Use grep_search to find relevant code by searching for keywords
    4. Identify what needs to be changed based on the review
    5. MAKE the changes using appropriate tool (insert_lines/save_file/replace/delete)
    6. VERIFY changes by reading the modified file to ensure it looks correct

    **Guidelines:**
    - You MUST call a write tool before returning (save_file/insert_lines/etc)
    - After editing, ALWAYS read the file again to verify changes are correct
    - If verification shows errors, fix them before returning
    - DO NOT return result without actually modifying/deleting files first
    - Address all issues mentioned in the review
    - Review feedback may contain errors or unreasonable suggestions - verify
        that changes make sense
    - If the review suggests something incorrect, explain why and provide
        a better solution
    - Follow existing code style and conventions
    - Make focused, clear changes
    - Write the comment in the same language as the review
    - You can edit .github/workflows files if necessary to fix the issues
""")


def run_code_agent_fixissue(issue: Issue, repo_path: Path) -> str:
    """Run code agent to fix issue and return PR description."""
    logger.info(f"Starting agent to fix issue #{issue.number}: {issue.title}")

    model = create_chat_model()
    tools = create_file_tools(repo_path)

    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT_FIXISSUE,
    )

    tool_call_limit = os.getenv("TC_AGENT_TOOL_CALL_LIMIT")
    if not tool_call_limit:
        raise ValueError("TC_AGENT_TOOL_CALL_LIMIT environment variable is not set")
    recursion_limit = int(tool_call_limit) * 2 + 10  # Each tool call = 2 steps

    user_message = dedent(f"""\
        Fix the following issue:

        **Issue title: {issue.title}**

        **Issue body:**

        {issue.body or "No description provided."}
    """)

    logger.debug(f"Running agent with recursion_limit={recursion_limit}")
    response = agent.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        {"recursion_limit": recursion_limit},
    )

    # Extract final message from response
    messages = response.get("messages", [])
    if not messages:
        raise ValueError("Agent response contains no messages")

    result = messages[-1].content
    logger.info("Agent completed fixing issue")

    return str(result)


def run_code_agent_fixpr(
    issue: Issue, pull_request: PullRequest, repo_path: Path
) -> str:
    """Run code agent to fix PR based on review feedback."""
    logger.info(f"Starting agent to fix PR #{pull_request.number}")

    # Get the latest review
    reviews = list(pull_request.get_reviews())
    if not reviews:
        logger.warning("No reviews found for this PR")
        latest_review_body = "No review comments available"
    else:
        latest_review = reviews[-1]
        latest_review_body = latest_review.body or "No review body provided"
        logger.debug(
            f"Latest review by {latest_review.user.login}: {latest_review.state}"
        )

    # Get code changes
    logger.debug("Fetching file changes from PR")
    changes = get_pr_changes(pull_request)

    model = create_chat_model()
    tools = create_file_tools(repo_path)

    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT_FIXPR,
    )

    tool_call_limit = os.getenv("TC_AGENT_TOOL_CALL_LIMIT")
    if not tool_call_limit:
        raise ValueError("TC_AGENT_TOOL_CALL_LIMIT environment variable is not set")
    recursion_limit = int(tool_call_limit) * 2 + 10

    user_message = dedent(f"""\
        Fix the following pull request based on review feedback:

        **PR #{pull_request.number}: {pull_request.title}**

        **Related Issue #{issue.number}: {issue.title}**
        {issue.body or "No description provided."}

        **Current Code Changes in PR:**
        ```json
        {json.dumps(changes, indent=2, ensure_ascii=False)}
        ```

        **Latest Review Feedback:**
        {latest_review_body}

        Please analyze the current changes, understand the feedback,
        and apply necessary fixes.
    """)

    logger.debug("Running fix PR agent")
    response = agent.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        {"recursion_limit": recursion_limit},
    )

    # Extract final message from response
    messages = response.get("messages", [])
    if not messages:
        raise ValueError("Agent response contains no messages")

    result = messages[-1].content
    logger.info("Agent completed fixes")

    return str(result)
