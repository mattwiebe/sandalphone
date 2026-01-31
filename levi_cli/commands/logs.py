"""Log management commands."""

import sys

import click
from rich.console import Console

from levi_cli.core.log_manager import LogManager
from levi_cli.core.project import get_project_paths
from levi_cli.utils.output import print_error, print_info

console = Console()


@click.group()
def logs():
    """
    View and manage logs.

    View logs from Mac backend and Telegram bot services.

    Examples:
        levi logs tail                      # Show recent logs from all services
        levi logs tail --service mac-backend -n 100  # Show 100 lines from Mac backend
        levi logs follow                    # Follow logs in real-time
    """
    pass


@logs.command()
@click.option(
    "--service",
    "-s",
    type=click.Choice(["mac-backend", "telegram-bot"], case_sensitive=False),
    help="Specific service logs to show (default: all)",
)
@click.option(
    "--lines",
    "-n",
    type=int,
    default=50,
    help="Number of lines to show (default: 50)",
)
@click.pass_context
def tail(ctx, service, lines):
    """
    Show recent log entries.

    Displays the last N lines from service log files.

    Examples:
        levi logs tail                      # Show 50 lines from all services
        levi logs tail -n 100               # Show 100 lines
        levi logs tail --service mac-backend  # Show Mac backend logs only
    """
    try:
        paths = get_project_paths()
        manager = LogManager(paths.logs_dir)

        if not paths.logs_dir.exists():
            print_error(f"Logs directory not found: {paths.logs_dir}")
            ctx.exit(1)

        # Determine which services to show
        if service:
            services = [service]
        else:
            services = ["mac-backend", "telegram-bot"]

        for svc in services:
            log_path = manager.get_log_path(svc)

            if not log_path.exists():
                print_error(f"Log file not found: {log_path}")
                continue

            # Print header
            console.print(f"\n[bold cyan]=== {svc.upper()} (last {lines} lines) ===[/bold cyan]\n")

            # Get and print log lines
            log_lines = manager.tail(svc, lines)

            for line in log_lines:
                # Colorize and print
                colored_line = manager.colorize_line(line.rstrip())
                print(colored_line)

    except RuntimeError as e:
        print_error(str(e))
        ctx.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")
        if ctx.obj.get("verbose"):
            console.print_exception()
        ctx.exit(1)


@logs.command()
@click.option(
    "--service",
    "-s",
    type=click.Choice(["mac-backend", "telegram-bot"], case_sensitive=False),
    help="Specific service logs to follow (default: all)",
)
@click.pass_context
def follow(ctx, service):
    """
    Follow logs in real-time.

    Watches log files and displays new entries as they're written (like tail -f).
    Press Ctrl+C to stop.

    Examples:
        levi logs follow                    # Follow all service logs
        levi logs follow --service telegram-bot  # Follow Telegram bot logs only
    """
    try:
        paths = get_project_paths()
        manager = LogManager(paths.logs_dir)

        if not paths.logs_dir.exists():
            print_error(f"Logs directory not found: {paths.logs_dir}")
            ctx.exit(1)

        # Determine which service to follow
        if not service:
            # Default to mac-backend if not specified
            service = "mac-backend"
            print_info(f"Following {service} logs (press Ctrl+C to stop)")

        log_path = manager.get_log_path(service)

        if not log_path.exists():
            print_info(f"Waiting for log file: {log_path}")

        # Follow the log file
        try:
            for line in manager.follow(service, colorize=True):
                print(line, end="")
                sys.stdout.flush()
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopped following logs[/yellow]")
            ctx.exit(0)

    except RuntimeError as e:
        print_error(str(e))
        ctx.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")
        if ctx.obj.get("verbose"):
            console.print_exception()
        ctx.exit(1)
