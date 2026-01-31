"""Main CLI entry point."""

import click
from rich.console import Console

from levi_cli.core.project import get_project_paths
from levi_cli.core.service_manager import LaunchAgentManager, ServiceName
from levi_cli.utils.output import print_error, print_table

console = Console()


@click.group(invoke_without_command=True)
@click.pass_context
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def cli(ctx, verbose):
    """
    Levi - Voice translation service management CLI.

    A command-line tool for managing Levi's Mac backend and Telegram bot services.

    Examples:
        levi status                    # Show service status
        levi services start            # Start all services
        levi logs follow               # Follow logs in real-time
        levi config show               # Show configuration
    """
    # Store verbose flag in context
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    # If no subcommand, run status by default
    if ctx.invoked_subcommand is None:
        ctx.invoke(status)


@cli.command()
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def status(ctx, output_json):
    """
    Show overall service status.

    Displays the current status of all Levi services including whether
    they're running, their PID, and last exit status.

    Examples:
        levi status              # Show status table
        levi status --json       # Output as JSON
    """
    try:
        # Get project paths
        paths = get_project_paths()

        # Create service manager
        manager = LaunchAgentManager(paths.root)

        # Get status for all services
        services = []
        for service_name in ServiceName:
            status = manager.get_status(service_name)
            services.append(
                {
                    "Service": service_name.display_name,
                    "Status": (status.status_str, status.status_color),
                    "PID": str(status.pid) if status.pid else "-",
                    "Last Exit": str(status.last_exit) if status.last_exit is not None else "-",
                }
            )

        if output_json:
            # Convert to JSON-friendly format
            json_data = []
            for s in services:
                status_val, _ = s["Status"] if isinstance(s["Status"], tuple) else (s["Status"], "")
                json_data.append(
                    {
                        "service": s["Service"],
                        "status": status_val,
                        "pid": s["PID"],
                        "last_exit": s["Last Exit"],
                    }
                )
            from levi_cli.utils.output import print_json

            print_json(json_data)
        else:
            print_table(services, title="Levi Services")

    except RuntimeError as e:
        print_error(str(e))
        ctx.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")
        if ctx.obj.get("verbose"):
            console.print_exception()
        ctx.exit(1)


# Import command groups
from levi_cli.commands.services import services
from levi_cli.commands.config import config
from levi_cli.commands.logs import logs

cli.add_command(services)
cli.add_command(config)
cli.add_command(logs)


if __name__ == "__main__":
    cli()
