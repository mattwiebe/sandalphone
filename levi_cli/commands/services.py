"""Service management commands."""

import click
from rich.console import Console

from levi_cli.core.project import get_project_paths
from levi_cli.core.service_manager import LaunchAgentManager, ServiceName
from levi_cli.utils.output import (
    print_error,
    print_json,
    print_success,
    print_table,
    print_warning,
)

console = Console()


@click.group()
def services():
    """
    Manage Levi services.

    Control the Mac backend and Telegram bot services using macOS LaunchAgents.

    Examples:
        levi services start            # Start all services
        levi services stop --service mac-backend  # Stop specific service
        levi services restart          # Restart all services
        levi services status --json    # Get status as JSON
    """
    pass


@services.command()
@click.option(
    "--service",
    "-s",
    type=click.Choice(["mac-backend", "telegram-bot"], case_sensitive=False),
    help="Specific service to start (default: all)",
)
@click.pass_context
def start(ctx, service):
    """
    Start Levi services.

    Starts one or all services using launchctl bootstrap.
    If a service is already running, it will be skipped.

    Examples:
        levi services start                      # Start all services
        levi services start --service mac-backend  # Start Mac backend only
    """
    try:
        paths = get_project_paths()
        manager = LaunchAgentManager(paths.root)

        # Determine which services to start
        if service:
            service_map = {
                "mac-backend": ServiceName.MAC_BACKEND,
                "telegram-bot": ServiceName.TELEGRAM_BOT,
            }
            services_to_start = [service_map[service]]
        else:
            services_to_start = list(ServiceName)

        # Start services
        errors = []
        for svc in services_to_start:
            success, message = manager.start(svc)
            if success:
                print_success(message)
            else:
                print_error(message)
                errors.append(message)

        if errors:
            ctx.exit(1)

    except RuntimeError as e:
        print_error(str(e))
        ctx.exit(1)


@services.command()
@click.option(
    "--service",
    "-s",
    type=click.Choice(["mac-backend", "telegram-bot"], case_sensitive=False),
    help="Specific service to stop (default: all)",
)
@click.pass_context
def stop(ctx, service):
    """
    Stop Levi services.

    Stops one or all services using launchctl bootout.

    Examples:
        levi services stop                      # Stop all services
        levi services stop --service telegram-bot  # Stop Telegram bot only
    """
    try:
        paths = get_project_paths()
        manager = LaunchAgentManager(paths.root)

        # Determine which services to stop
        if service:
            service_map = {
                "mac-backend": ServiceName.MAC_BACKEND,
                "telegram-bot": ServiceName.TELEGRAM_BOT,
            }
            services_to_stop = [service_map[service]]
        else:
            services_to_stop = list(ServiceName)

        # Stop services
        errors = []
        for svc in services_to_stop:
            success, message = manager.stop(svc)
            if success:
                print_success(message)
            else:
                print_error(message)
                errors.append(message)

        if errors:
            ctx.exit(1)

    except RuntimeError as e:
        print_error(str(e))
        ctx.exit(1)


@services.command()
@click.option(
    "--service",
    "-s",
    type=click.Choice(["mac-backend", "telegram-bot"], case_sensitive=False),
    help="Specific service to restart (default: all)",
)
@click.pass_context
def restart(ctx, service):
    """
    Restart Levi services.

    Restarts one or all services using launchctl kickstart.
    This kills the process and lets LaunchAgent restart it.

    Examples:
        levi services restart                      # Restart all services
        levi services restart --service mac-backend  # Restart Mac backend only
    """
    try:
        paths = get_project_paths()
        manager = LaunchAgentManager(paths.root)

        # Determine which services to restart
        if service:
            service_map = {
                "mac-backend": ServiceName.MAC_BACKEND,
                "telegram-bot": ServiceName.TELEGRAM_BOT,
            }
            services_to_restart = [service_map[service]]
        else:
            services_to_restart = list(ServiceName)

        # Restart services
        errors = []
        for svc in services_to_restart:
            success, message = manager.restart(svc)
            if success:
                print_success(message)
            else:
                print_error(message)
                errors.append(message)

        if errors:
            ctx.exit(1)

    except RuntimeError as e:
        print_error(str(e))
        ctx.exit(1)


@services.command()
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def status(ctx, output_json):
    """
    Show service status.

    Displays the current status of all Levi services.

    Examples:
        levi services status       # Show status table
        levi services status --json  # Output as JSON
    """
    try:
        paths = get_project_paths()
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
            print_json(json_data)
        else:
            print_table(services, title="Levi Services")

    except RuntimeError as e:
        print_error(str(e))
        ctx.exit(1)


@services.command()
@click.option(
    "--service",
    "-s",
    type=click.Choice(["mac-backend", "telegram-bot"], case_sensitive=False),
    help="Specific service to enable (default: all)",
)
@click.pass_context
def enable(ctx, service):
    """
    Enable (install) Levi service plists.

    Copies plist files from scripts/ to ~/Library/LaunchAgents/.
    This is required before services can be started.

    Examples:
        levi services enable                      # Enable all services
        levi services enable --service mac-backend  # Enable Mac backend only
    """
    try:
        paths = get_project_paths()
        manager = LaunchAgentManager(paths.root)

        # Determine which services to enable
        if service:
            service_map = {
                "mac-backend": ServiceName.MAC_BACKEND,
                "telegram-bot": ServiceName.TELEGRAM_BOT,
            }
            services_to_enable = [service_map[service]]
        else:
            services_to_enable = list(ServiceName)

        # Enable services
        errors = []
        for svc in services_to_enable:
            success, message = manager.install_plist(svc)
            if success:
                print_success(message)
            else:
                print_error(message)
                errors.append(message)

        if errors:
            ctx.exit(1)
        else:
            print_warning("Plists installed. Run 'levi services start' to start services.")

    except RuntimeError as e:
        print_error(str(e))
        ctx.exit(1)


@services.command()
@click.option(
    "--service",
    "-s",
    type=click.Choice(["mac-backend", "telegram-bot"], case_sensitive=False),
    help="Specific service to disable (default: all)",
)
@click.pass_context
def disable(ctx, service):
    """
    Disable (uninstall) Levi service plists.

    Stops services and removes plist files from ~/Library/LaunchAgents/.

    Examples:
        levi services disable                      # Disable all services
        levi services disable --service telegram-bot  # Disable Telegram bot only
    """
    try:
        paths = get_project_paths()
        manager = LaunchAgentManager(paths.root)

        # Determine which services to disable
        if service:
            service_map = {
                "mac-backend": ServiceName.MAC_BACKEND,
                "telegram-bot": ServiceName.TELEGRAM_BOT,
            }
            services_to_disable = [service_map[service]]
        else:
            services_to_disable = list(ServiceName)

        # Disable services
        errors = []
        for svc in services_to_disable:
            success, message = manager.uninstall_plist(svc)
            if success:
                print_success(message)
            else:
                print_error(message)
                errors.append(message)

        if errors:
            ctx.exit(1)

    except RuntimeError as e:
        print_error(str(e))
        ctx.exit(1)
