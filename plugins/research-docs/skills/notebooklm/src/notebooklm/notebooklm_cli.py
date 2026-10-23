"""CLI interface for NotebookLM automation.

Command structure:
  notebooklm login                    # Authenticate
  notebooklm use <notebook_id>        # Set current notebook context
  notebooklm status                   # Show current context
  notebooklm list                     # List notebooks
  notebooklm create <title>           # Create notebook
  notebooklm copy <title>             # Copy current notebook
  notebooklm ask <question>           # Ask the current notebook a question

  notebooklm source <command>         # Source operations
  notebooklm artifact <command>       # Artifact management
  notebooklm generate <type>          # Generate content
  notebooklm download <type>          # Download content
  notebooklm note <command>           # Note operations
  notebooklm research <command>       # Research status/wait

Architecture:
    - This module is the entry-point assembler invoked via the ``notebooklm``
      console script (see ``[project.scripts]`` in ``pyproject.toml``).
    - It imports command groups from the ``notebooklm.cli`` package and
      registers them on the top-level Click group ``notebooklm``.
    - The ``cli/`` package contains the actual command implementations
      (``*_cmd.py`` modules for command groups and top-level command
      registration; shared runtime helpers live in sibling modules such as
      ``options.py``, ``runtime.py``, and ``auth_runtime.py``).
    - Editing CLI behavior: change the relevant ``cli/*_cmd.py`` module or
      shared helper. Editing CLI surface (adding a new top-level command):
      import + register it here.

LLM-friendly design:
  # Set context once, then use simple commands
  notebooklm use nb123
  notebooklm generate video "a funny explainer for kids"
  notebooklm generate audio "deep dive focusing on chapter 3"
  notebooklm ask "what are the key themes?"
"""

# Runtime Python version guard (must run before any PEP 604 syntax is evaluated)
import sys

from ._version_check import check_python_version as _check_python_version

_check_python_version()
del _check_python_version

import logging
import os
import warnings
from pathlib import Path

# =============================================================================
# WINDOWS COMPATIBILITY FIXES (issue #75, #79, #80, #318)
# Must be applied before any async code runs
# =============================================================================


def _reconfigure_output_stream(stream) -> None:
    """Use UTF-8 with replacement for active Windows text streams."""
    if stream is None:
        return
    reconfigure = getattr(stream, "reconfigure", None)
    if not callable(reconfigure):
        return
    try:
        reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, TypeError, ValueError):
        # best-effort: stdout.reconfigure unavailable on this platform.
        pass


def _configure_windows_runtime() -> None:
    """Apply Windows runtime fixes before Click and Rich command modules load."""
    if sys.platform != "win32":
        return

    # The event loop is no longer chosen here. Commands run on asyncio's default
    # (Proactor) loop unless NOTEBOOKLM_WINDOWS_EVENT_LOOP opts into the selector
    # loop (#79); see cli/runtime.py.

    # Fix #80/#318: changing PYTHONUTF8 after startup does not update the already
    # created stdout/stderr TextIOWrappers. Reconfigure the live streams so Rich's
    # legacy Windows renderer can write emoji and other Unicode output safely.
    os.environ.setdefault("PYTHONUTF8", "1")
    _reconfigure_output_stream(sys.stdout)
    _reconfigure_output_stream(sys.stderr)


_configure_windows_runtime()

import click

from ._version_info import version_string

# Import command groups from cli package
from .cli import (
    agent,
    artifact,
    collection,
    download,
    generate,
    label,
    language,
    mcp,
    note,
    profile,
    register_chat_commands,
    register_doctor_command,
    register_notebook_commands,
    # Register functions for top-level commands
    register_session_commands,
    research,
    share,
    skill,
    source,
    usage,
)
from .cli.grouped import ConfigurationClickException, SectionedGroup

# Public surface (ADR-0012). ``main`` is the ``[project.scripts]`` entry
# point and ``src/notebooklm/__main__.py`` shim; ``cli`` is the root
# ``click.Group`` imported by tests to drive ``CliRunner`` invocations.
# The underscore-prefixed helpers in this module (``_reconfigure_output_stream``,
# ``_configure_windows_runtime``) stay importable for tests but are not part
# of the documented public API.
__all__ = ["cli", "main"]


# =============================================================================
# MAIN CLI GROUP
# =============================================================================


@click.group(cls=SectionedGroup)
@click.version_option(version=version_string(), prog_name="NotebookLM CLI")
@click.option(
    "--storage",
    type=click.Path(exists=False),
    default=None,
    help="Path to storage_state.json (default: ~/.notebooklm/profiles/<profile>/storage_state.json)",
)
@click.option(
    "-p",
    "--profile",
    default=None,
    help="Profile name (default: from config or 'default'). Use 'notebooklm profile list' to see profiles.",
)
@click.option(
    "--backend",
    type=click.Choice(("web", "android"), case_sensitive=True),
    default=None,
    help="Preferred API backend (default: $NOTEBOOKLM_BACKEND, else web).",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (-v for INFO, -vv for DEBUG)",
)
@click.option(
    "--quiet",
    is_flag=True,
    default=False,
    help=(
        "Suppress status output and INFO/WARN log records (only errors survive). "
        "Mutually exclusive with -v/-vv."
    ),
)
@click.pass_context
def cli(ctx, storage, profile, backend, verbose, quiet):
    """NotebookLM CLI.

    \b
    Quick start:
      notebooklm login              # Authenticate first
      notebooklm list               # List your notebooks
      notebooklm create "My Notes"  # Create a notebook
      notebooklm ask "Hi"           # Ask the current notebook a question

    \b
    Tip: Use partial notebook IDs (e.g., 'notebooklm use abc' matches 'abc123...')
    """
    # ``--quiet`` and ``-v/-vv`` resolve to incompatible log-level intents
    # (ERROR vs INFO/DEBUG). Honoring either silently would surprise the
    # other caller; reject the conflict explicitly so the user can drop one
    # flag.
    if quiet and verbose:
        raise click.UsageError("--quiet and -v are mutually exclusive.")

    # Configure logging based on verbosity: -v for INFO, -vv+ for DEBUG.
    # ``--quiet`` raises the floor to ERROR so cron / CI logs stay clean
    # while still surfacing real failures.
    if quiet:
        logging.getLogger("notebooklm").setLevel(logging.ERROR)
    elif verbose >= 2:
        logging.getLogger("notebooklm").setLevel(logging.DEBUG)
        # DEBUG logging on httpx/urllib3 emits full URLs and headers — install
        # redaction so credentials don't leak via third-party loggers.
        from .log import install_redaction

        install_redaction("httpx", "urllib3")
    elif verbose == 1:
        logging.getLogger("notebooklm").setLevel(logging.INFO)

    # Reject a bad NOTEBOOKLM_WINDOWS_EVENT_LOOP before a command does work it
    # would throw away (e.g. an interactive login whose result it never saves).
    from .cli.runtime import windows_event_loop_choice
    from .exceptions import ConfigurationError

    try:
        loop_choice = windows_event_loop_choice()
    except ConfigurationError as e:
        raise ConfigurationClickException(str(e)) from None
    if sys.platform == "win32":
        logging.getLogger(__name__).debug(
            "Windows event loop: %s", loop_choice or "proactor (asyncio default)"
        )
    if loop_choice == "selector":
        # Fix #2485: on CPython 3.12-3.14 the selector transport drops a chunk
        # when a Windows send() would block, corrupting large uploads. Install
        # the fix CPython 3.15 shipped; a no-op on interpreters without the bug.
        from ._windows_asyncio import install_selector_write_fix

        install_selector_write_fix()

    # Set up profile system
    from .paths import set_active_profile

    # Always reset to prevent leaking across CliRunner invocations
    set_active_profile(profile)

    # Only set up profiles dir when not using an explicit auth source.
    # ``--storage`` and the env-var auth fast path bypass the profile system
    # entirely and must not require a writable NOTEBOOKLM_HOME. The env-var
    # check goes through :mod:`cli.services.auth_source` so the precedence
    # logic stays in one place.
    from .cli.services.auth_source import has_env_auth_json

    if not storage and not has_env_auth_json():
        try:
            from .migration import ensure_profiles_dir

            ensure_profiles_dir()
        except ValueError as e:
            # Invalid profile name (e.g., path traversal in env var or config)
            import click as _click

            raise _click.ClickException(str(e)) from None

    ctx.ensure_object(dict)
    # Canonicalize once at the boundary: ``--storage ~/foo.json`` and
    # ``--storage /Users/x/foo.json`` must map to the same sibling-context
    # namespace (see :class:`notebooklm.cli.services.auth_source.AuthSource`).
    ctx.obj["storage_path"] = Path(storage).expanduser().resolve() if storage else None
    ctx.obj["profile"] = profile
    ctx.obj["backend"] = backend
    # Mirror the root quiet flag for call sites that already read ctx.obj.
    # ``cli.runtime.is_quiet(ctx)`` remains the canonical reader.
    ctx.obj["quiet"] = bool(quiet)
    # Default client factory: commands resolve ``NotebookLMClient`` through
    # ``cli.auth_runtime.resolve_client_factory``. ``setdefault`` never clobbers a
    # factory injected via ``CliRunner.invoke(obj=...)`` (the test seam); ``None``
    # leaves resolution to the call-site default / lazy real client.
    ctx.obj.setdefault("client_factory", None)


# =============================================================================
# REGISTER COMMANDS
# =============================================================================

# Register top-level commands from modules
register_session_commands(cli)
register_notebook_commands(cli)
register_chat_commands(cli)
register_doctor_command(cli)

# Register command groups (subcommand style)
cli.add_command(source)
cli.add_command(artifact)
cli.add_command(agent)
cli.add_command(generate)
cli.add_command(download)
cli.add_command(note)
cli.add_command(label)
cli.add_command(collection)
cli.add_command(share)
cli.add_command(skill)
cli.add_command(research)
cli.add_command(language)
cli.add_command(profile)
cli.add_command(mcp)
cli.add_command(usage)


# =============================================================================
# SHELL COMPLETION
# =============================================================================


@cli.command("completion")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def completion_cmd(shell: str) -> None:
    """Print the shell completion script for SHELL.

    Pipe the output into a file your shell sources at startup. Click handles
    the ``_NOTEBOOKLM_COMPLETE`` env-var protocol automatically once the
    script is sourced; only the script needs to be installed.

    \b
    Install (one-time):
      # bash (~/.bashrc)
      notebooklm completion bash > ~/.notebooklm-complete.bash
      echo 'source ~/.notebooklm-complete.bash' >> ~/.bashrc

      # zsh (anywhere on $fpath)
      notebooklm completion zsh > ~/.zfunc/_notebooklm

      # fish
      notebooklm completion fish > ~/.config/fish/completions/notebooklm.fish

    Then ``notebooklm <cmd> -n <TAB>`` lists notebook IDs from the active
    profile (best-effort — no suggestions when not authenticated).
    """
    # Click ships shell-specific completion classes that emit the script
    # body. We just print whatever ``source()`` returns and let the user
    # redirect it themselves; auto-installing into shell configs would be
    # too magical and would hide the install path from users who care.
    from click.shell_completion import BashComplete, FishComplete, ZshComplete

    cls_map = {"bash": BashComplete, "zsh": ZshComplete, "fish": FishComplete}
    completer_cls = cls_map[shell]
    completer = completer_cls(cli, {}, "notebooklm", "_NOTEBOOKLM_COMPLETE")
    click.echo(completer.source())


# ``completion`` is a one-time install command (like ``login``) so it lives
# in the Session section. The binning is declared in
# ``cli/grouped.py::SectionedGroup.command_sections`` so the no-orphans
# guardrail in ``tests/unit/cli/test_grouped.py`` finds it.


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def _hide_curl_cffi_proactor_advice() -> None:
    """Hide curl_cffi's Proactor warning in a Windows CLI process.

    On the Proactor loop curl_cffi starts a helper selector thread and warns,
    advising the selector policy this CLI no longer installs because of #2485.
    The fallback works, so the advice only misleads. Installed from ``main()``
    rather than at import, so applications importing this module keep their
    own warning filters.
    """
    if sys.platform == "win32":
        warnings.filterwarnings(
            "ignore",
            message=r"\s*Proactor event loop does not implement add_reader",
            category=UserWarning,
        )


def main():
    _hide_curl_cffi_proactor_advice()
    cli()


if __name__ == "__main__":
    main()
