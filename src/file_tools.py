"""Custom file tools for LangChain agents."""

import json
import logging
from pathlib import Path

from langchain_core.tools import tool

logger = logging.getLogger("tishcode")

# Global variable to store base directory (set by create_file_tools)
_base_dir: Path | None = None


def _check_path(relative_path: str) -> tuple[bool, Path]:
    """Check if the file path is within the base directory."""
    if _base_dir is None:
        return False, Path()
    try:
        resolved = (_base_dir / relative_path).resolve()
        if _base_dir.resolve() in resolved.parents or resolved == _base_dir.resolve():
            return True, resolved
        return False, _base_dir
    except Exception:
        return False, _base_dir


def _log_result(tool_name: str, result: str) -> str:
    """Log tool result at debug level and return it."""
    # Truncate long results for logging
    log_result = result[:500] + "..." if len(result) > 500 else result
    logger.debug(f"[{tool_name}] Result: {log_result}")
    return result


@tool
def read_file(file_name: str) -> str:
    """Read the entire contents of a file.

    Args:
        file_name: Path to the file relative to repository root (e.g. "src/main.py")
    """
    logger.debug(f"[read_file] file_name={file_name}")
    safe, file_path = _check_path(file_name)
    if not safe:
        logger.error(f"Attempted to read file outside base directory: {file_name}")
        return _log_result("read_file", "Error: Cannot read file outside repository")
    try:
        result = file_path.read_text(encoding="utf-8")
        return _log_result("read_file", result)
    except FileNotFoundError:
        return _log_result("read_file", f"Error: File not found: {file_name}")
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        return _log_result("read_file", f"Error reading file: {e}")


@tool
def read_file_chunk(file_name: str, start_line: int, end_line: int) -> str:
    """Read a portion of a file from start_line to end_line (inclusive, 1-indexed).

    Args:
        file_name: Path to the file relative to repository root
        start_line: First line to read (1-indexed)
        end_line: Last line to read (1-indexed, inclusive)
    """
    logger.debug(
        f"[read_file_chunk] file_name={file_name}, "
        f"start_line={start_line}, end_line={end_line}"
    )
    safe, file_path = _check_path(file_name)
    if not safe:
        logger.error(f"Attempted to read file outside base directory: {file_name}")
        return _log_result(
            "read_file_chunk", "Error: Cannot read file outside repository"
        )
    try:
        contents = file_path.read_text(encoding="utf-8")
        lines = contents.split("\n")
        total_lines = len(lines)

        # Validate line numbers (1-indexed)
        if start_line < 1 or end_line < 1:
            return _log_result(
                "read_file_chunk", "Error: Line numbers must be >= 1"
            )
        if start_line > end_line:
            return _log_result(
                "read_file_chunk", "Error: start_line must be <= end_line"
            )
        if start_line > total_lines:
            return _log_result(
                "read_file_chunk",
                f"Error: start_line {start_line} exceeds file length ({total_lines})",
            )

        # Convert to 0-indexed and slice
        chunk_lines = lines[start_line - 1 : end_line]
        result = "\n".join(chunk_lines)
        return _log_result("read_file_chunk", result)
    except FileNotFoundError:
        return _log_result("read_file_chunk", f"Error: File not found: {file_name}")
    except Exception as e:
        logger.error(f"Error reading file chunk: {e}")
        return _log_result("read_file_chunk", f"Error reading file chunk: {e}")


@tool
def save_file(file_name: str, contents: str) -> str:
    """Create or overwrite a file with the given contents.

    Args:
        file_name: Path to the file relative to repository root (e.g. "src/main.py")
        contents: The full contents to write to the file
    """
    logger.debug(f"[save_file] file_name={file_name}, contents_len={len(contents)}")
    safe, file_path = _check_path(file_name)
    if not safe:
        logger.error(f"Attempted to save file outside base directory: {file_name}")
        return _log_result("save_file", "Error: Cannot save file outside repository")
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(contents, encoding="utf-8")
        logger.info(f"Saved file: {file_name}")
        return _log_result("save_file", f"Successfully saved file: {file_name}")
    except Exception as e:
        logger.error(f"Error saving file: {e}")
        return _log_result("save_file", f"Error saving file: {e}")


@tool
def replace_file_chunk(
    file_name: str, start_line: int, end_line: int, new_content: str
) -> str:
    """Replace lines from start_line to end_line with new content (1-indexed).

    Args:
        file_name: Path to the file relative to repository root
        start_line: First line to replace (1-indexed)
        end_line: Last line to replace (1-indexed, inclusive)
        new_content: New content to insert (can be multiple lines)
    """
    logger.debug(
        f"[replace_file_chunk] file_name={file_name}, "
        f"start_line={start_line}, end_line={end_line}, "
        f"new_content_len={len(new_content)}"
    )
    safe, file_path = _check_path(file_name)
    if not safe:
        logger.error(f"Attempted to modify file outside base directory: {file_name}")
        return _log_result(
            "replace_file_chunk", "Error: Cannot modify file outside repository"
        )
    try:
        contents = file_path.read_text(encoding="utf-8")
        lines = contents.split("\n")
        total_lines = len(lines)

        # Validate line numbers (1-indexed)
        if start_line < 1 or end_line < 1:
            return _log_result(
                "replace_file_chunk", "Error: Line numbers must be >= 1"
            )
        if start_line > end_line:
            return _log_result(
                "replace_file_chunk", "Error: start_line must be <= end_line"
            )
        if start_line > total_lines:
            return _log_result(
                "replace_file_chunk",
                f"Error: start_line {start_line} exceeds file length ({total_lines})",
            )

        # Replace lines (convert to 0-indexed)
        before = lines[: start_line - 1]
        after = lines[end_line:]
        new_lines = new_content.split("\n") if new_content else []

        result_lines = before + new_lines + after
        new_contents = "\n".join(result_lines)

        file_path.write_text(new_contents, encoding="utf-8")
        logger.info(
            f"Replaced lines {start_line}-{end_line} in {file_name}"
        )
        return _log_result(
            "replace_file_chunk",
            f"Successfully replaced lines {start_line}-{end_line} in {file_name}",
        )
    except FileNotFoundError:
        return _log_result(
            "replace_file_chunk", f"Error: File not found: {file_name}"
        )
    except Exception as e:
        logger.error(f"Error replacing file chunk: {e}")
        return _log_result("replace_file_chunk", f"Error replacing file chunk: {e}")


@tool
def delete_file(file_name: str) -> str:
    """Delete a file from the repository.

    Args:
        file_name: Path to the file relative to repository root (e.g. "src/old_file.py")
    """
    logger.debug(f"[delete_file] file_name={file_name}")
    safe, file_path = _check_path(file_name)
    if not safe:
        logger.error(f"Attempted to delete file outside base directory: {file_name}")
        return _log_result(
            "delete_file", "Error: Cannot delete file outside repository"
        )
    try:
        if file_path.is_dir():
            file_path.rmdir()
        else:
            file_path.unlink()
        logger.info(f"Deleted file: {file_name}")
        return _log_result("delete_file", f"Successfully deleted: {file_name}")
    except FileNotFoundError:
        return _log_result("delete_file", f"Error: File not found: {file_name}")
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        return _log_result("delete_file", f"Error deleting file: {e}")


@tool
def list_files(directory: str = ".") -> str:
    """List files and directories in the given directory.

    Args:
        directory: Path to directory relative to repository root (e.g. "src" or ".")
    """
    logger.debug(f"[list_files] directory={directory}")
    safe, dir_path = _check_path(directory)
    if not safe:
        logger.error(f"Attempted to list files outside base directory: {directory}")
        return _log_result(
            "list_files", "Error: Cannot list files outside repository"
        )
    try:
        if not dir_path.is_dir():
            return _log_result("list_files", f"Error: Not a directory: {directory}")
        files = [str(f.relative_to(_base_dir)) for f in dir_path.iterdir()]
        result = json.dumps(files, indent=2)
        return _log_result("list_files", result)
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        return _log_result("list_files", f"Error listing files: {e}")


@tool
def search_files(pattern: str) -> str:
    """Search for files matching a glob pattern.

    Args:
        pattern: Glob pattern to match (e.g. "**/*.py", ".github/workflows/*.yml")
    """
    logger.debug(f"[search_files] pattern={pattern}")
    if _base_dir is None:
        return _log_result("search_files", "Error: Base directory not set")
    try:
        matching_files = list(_base_dir.glob(pattern))
        file_paths = [
            str(f.relative_to(_base_dir)) for f in matching_files if f.is_file()
        ]
        result = {
            "pattern": pattern,
            "matches_found": len(file_paths),
            "files": file_paths,
        }
        return _log_result("search_files", json.dumps(result, indent=2))
    except Exception as e:
        logger.error(f"Error searching files: {e}")
        return _log_result("search_files", f"Error searching files: {e}")


def create_file_tools(base_dir: Path) -> list:
    """Create file tools configured for the given base directory."""
    global _base_dir
    _base_dir = base_dir.resolve()
    logger.debug(f"File tools configured with base directory: {_base_dir}")
    return [
        read_file,
        read_file_chunk,
        save_file,
        replace_file_chunk,
        delete_file,
        list_files,
        search_files,
    ]
