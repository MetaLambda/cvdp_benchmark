# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Claude Code (headless mode) model instance for CVDP Benchmark.

Uses the `claude` CLI in headless/print mode to send prompts and receive responses,
bypassing direct API calls. This allows users to leverage their existing Claude Code
installation and authentication without needing separate API keys.

Requirements:
    - Claude Code CLI installed and authenticated (`claude` command available in PATH)
    - Run `claude --version` to verify installation
    - Run `claude` interactively once to complete authentication if needed
"""

import os
import logging
import json
import subprocess
import re
from typing import Optional, Any, List, Tuple, Dict
from src.config_manager import config
from src.model_helpers import ModelHelpers

logging.basicConfig(level=logging.INFO)


class ClaudeCodeInstance:
    """
    Model instance that uses Claude Code CLI in headless (--print) mode.

    Instead of calling the Anthropic API directly, this sends prompts through
    the `claude` CLI tool, which handles authentication, rate limiting, and
    model selection internally.
    """

    def __init__(self, context: str = "You are a helpful assistant.",
                 key: Optional[str] = None, model: str = "claude-code"):
        """
        Initialize the Claude Code headless model instance.

        Args:
            context: The system prompt or context for the model
            key: Not used (Claude Code handles its own authentication)
            model: Model identifier. Use "claude-code" for default, or
                   "claude-code-opus", "claude-code-sonnet" to select a
                   specific underlying model.
        """
        self.context = context
        self.model = model
        self.debug = False

        # Map model names to Claude Code --model flags
        self._model_map = {
            "claude-code": None,  # Use Claude Code's default model
            "claude-code-opus": "claude-opus-4-6",
            "claude-code-sonnet": "claude-sonnet-4-6",
            "claude-code-haiku": "claude-haiku-4-5-20251001",
        }

        # Determine the underlying model to pass to claude CLI
        self._claude_model = self._model_map.get(model)

        # Additional CLI options configurable via environment
        self._max_turns = int(os.environ.get("CLAUDE_CODE_MAX_TURNS", "1"))

        # Verify claude CLI is available
        self._verify_cli()

        logging.info(f"Created ClaudeCodeInstance (headless mode). Model flag: {self._claude_model or 'default'}")

    def _verify_cli(self):
        """Verify that the claude CLI is installed and accessible."""
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                logging.info(f"Claude Code CLI found: {version}")
            else:
                logging.warning(f"Claude Code CLI returned non-zero exit code: {result.stderr}")
        except FileNotFoundError:
            raise RuntimeError(
                "Claude Code CLI ('claude') not found in PATH. "
                "Install it with: npm install -g @anthropic-ai/claude-code\n"
                "Then authenticate by running 'claude' interactively once."
            )
        except subprocess.TimeoutExpired:
            logging.warning("Claude Code CLI version check timed out, proceeding anyway")

    def set_debug(self, debug: bool = True) -> None:
        """Enable or disable debug mode."""
        self.debug = debug
        logging.info(f"Debug mode {'enabled' if debug else 'disabled'}")

    @property
    def requires_evaluation(self) -> bool:
        """This model produces real responses that need harness evaluation."""
        return True

    def key(self, key: str):
        """No-op: Claude Code manages its own authentication."""
        pass

    def prompt(self, prompt: str, schema: Optional[str] = None, prompt_log: str = "",
               files: Optional[list] = None, timeout: int = 60,
               category: Optional[int] = None) -> Tuple[Any, bool]:
        """
        Send a prompt to Claude Code in headless mode and get a response.

        Args:
            prompt: The user prompt/query
            schema: Optional JSON schema for structured output
            prompt_log: Path to log the prompt (if not empty)
            files: List of expected output files (if any)
            timeout: Timeout in seconds for the CLI call
            category: Optional integer indicating the category/problem ID

        Returns:
            Tuple of (parsed_response, success_flag)
        """
        helper = ModelHelpers()
        system_prompt = helper.create_system_prompt(self.context, schema, category)

        # Use timeout from config if not specified
        if timeout == 60:
            timeout = config.get("MODEL_TIMEOUT", 60)

        # Determine if we're expecting a single file (direct text mode)
        expected_single_file = files and len(files) == 1 and schema is None

        if self.debug:
            logging.debug(f"Claude Code headless prompt")
            logging.debug(f"System prompt: {system_prompt}")
            logging.debug(f"User prompt: {prompt}")
            logging.debug(f"Timeout: {timeout}s")
            if files:
                logging.debug(f"Expected files: {files}")

        # Write prompt log
        if prompt_log:
            try:
                os.makedirs(os.path.dirname(prompt_log), exist_ok=True)
                temp_log = f"{prompt_log}.tmp"
                with open(temp_log, "w+") as f:
                    f.write(system_prompt + "\n\n----------------------------------------\n" + prompt)
                os.replace(temp_log, prompt_log)
            except Exception as e:
                logging.error(f"Failed to write prompt log to {prompt_log}: {str(e)}")
                raise

        # Call Claude Code CLI with separate system and user prompts
        content = self._call_claude_cli(prompt, system_prompt, timeout)

        if content is None:
            return {}, False

        if self.debug:
            logging.debug(f"Claude Code response (first 500 chars): {content[:500]}")

        # Process the response using ModelHelpers
        if expected_single_file:
            pass
        elif schema is not None and content.startswith('{') and content.endswith('}'):
            content = helper.fix_json_formatting(content)

        return helper.parse_model_response(content, files, expected_single_file)

    def _call_claude_cli(self, user_prompt: str, system_prompt: str, timeout: int) -> Optional[str]:
        """
        Call the claude CLI in headless mode.

        Uses the syntax: claude -p "user prompt" --append-system-prompt "system prompt"
        where -p (--print) enables headless mode and the user prompt is a positional argument.

        Args:
            user_prompt: The user prompt to send
            system_prompt: The system prompt to prepend
            timeout: Timeout in seconds

        Returns:
            The response text, or None on failure
        """
        # Build command: claude -p [options] "prompt"
        # -p / --print enables headless mode; the prompt is a positional arg
        cmd = ["claude", "-p"]

        # Add model flag if specified
        if self._claude_model:
            cmd.extend(["--model", self._claude_model])

        # Set max turns for single-turn benchmark queries
        cmd.extend(["--max-turns", str(self._max_turns)])

        # Use text output format for clean response
        cmd.extend(["--output-format", "text"])

        # Set system prompt (appended to Claude Code's default system prompt)
        if system_prompt:
            cmd.extend(["--append-system-prompt", system_prompt])

        # The user prompt is the positional argument (must come last)
        cmd.append(user_prompt)

        if self.debug:
            logging.debug(f"Claude Code CLI command: {cmd[0]} -p [options] <prompt>")
            logging.debug(f"Full command args count: {len(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                logging.error(f"Claude Code CLI failed (exit code {result.returncode}): {error_msg}")

                # Check for common issues
                if "not authenticated" in error_msg.lower() or "login" in error_msg.lower():
                    logging.error("Authentication issue. Run 'claude' interactively to authenticate.")
                elif "rate limit" in error_msg.lower():
                    logging.error("Rate limited. Consider reducing --threads or adding delays.")

                raise ValueError(f"Claude Code CLI error: {error_msg}")

            content = result.stdout.strip()
            if not content:
                logging.error("Empty response from Claude Code CLI")
                raise ValueError("Empty response from Claude Code CLI")

            return content

        except subprocess.TimeoutExpired:
            logging.error(f"Claude Code CLI timed out after {timeout}s")
            raise ValueError(f"Claude Code CLI timed out after {timeout}s")
        except FileNotFoundError:
            raise RuntimeError("Claude Code CLI ('claude') not found. Install with: npm install -g @anthropic-ai/claude-code")
