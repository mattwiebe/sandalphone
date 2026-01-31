"""Configuration management commands."""

import click
from rich.console import Console

from levi_cli.core.config_manager import CloudConfig, MacConfig
from levi_cli.core.project import get_project_paths
from levi_cli.utils.output import print_error, print_json, print_key_value, print_success, print_warning

console = Console()


@click.group()
def config():
    """
    Manage Levi configuration.

    View, validate, and edit configuration files for Mac backend and Telegram bot.

    Examples:
        levi config show                    # Show all configuration
        levi config show --service mac     # Show Mac backend config only
        levi config validate               # Validate all configuration
        levi config show --no-redact       # Show unredacted config
    """
    pass


@config.command()
@click.option(
    "--service",
    "-s",
    type=click.Choice(["mac", "cloud"], case_sensitive=False),
    help="Specific service configuration to show (default: all)",
)
@click.option("--no-redact", is_flag=True, help="Show sensitive values unredacted")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def show(ctx, service, no_redact, output_json):
    """
    Show configuration.

    Displays configuration for Mac backend and/or Telegram bot.
    By default, sensitive values (tokens, API keys) are redacted.

    Examples:
        levi config show                    # Show all config (redacted)
        levi config show --no-redact        # Show unredacted
        levi config show --service mac      # Show Mac config only
        levi config show --json             # Output as JSON
    """
    try:
        paths = get_project_paths()
        redact = not no_redact

        config_data = {}

        # Load Mac config if requested or if showing all
        if service is None or service == "mac":
            mac_config = MacConfig.from_env(paths.mac_env)
            config_data["mac"] = mac_config.to_dict(redact=redact)

        # Load Cloud config if requested or if showing all
        if service is None or service == "cloud":
            cloud_config = CloudConfig.from_env(paths.cloud_env)
            config_data["cloud"] = cloud_config.to_dict(redact=redact)

        if output_json:
            print_json(config_data)
        else:
            # Pretty print
            for service_name, config in config_data.items():
                console.print(f"\n[bold cyan]{service_name.upper()} Configuration:[/bold cyan]")
                for key, value in config.items():
                    print_key_value(key, value)

    except RuntimeError as e:
        print_error(str(e))
        ctx.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")
        if ctx.obj.get("verbose"):
            console.print_exception()
        ctx.exit(1)


@config.command()
@click.option(
    "--service",
    "-s",
    type=click.Choice(["mac", "cloud"], case_sensitive=False),
    help="Specific service configuration to validate (default: all)",
)
@click.pass_context
def validate(ctx, service):
    """
    Validate configuration.

    Checks that all required configuration values are present and valid.

    Examples:
        levi config validate                # Validate all config
        levi config validate --service cloud  # Validate cloud config only
    """
    try:
        paths = get_project_paths()
        all_valid = True
        errors_found = []

        # Validate Mac config if requested or if validating all
        if service is None or service == "mac":
            console.print("\n[bold]Mac Backend Configuration:[/bold]")

            if not paths.mac_env.exists():
                print_error(f"Configuration file not found: {paths.mac_env}")
                all_valid = False
            else:
                mac_config = MacConfig.from_env(paths.mac_env)
                errors = mac_config.validate()

                if errors:
                    for error in errors:
                        print_error(error)
                    all_valid = False
                    errors_found.extend(errors)
                else:
                    print_success("Mac configuration is valid")

        # Validate Cloud config if requested or if validating all
        if service is None or service == "cloud":
            console.print("\n[bold]Cloud Bot Configuration:[/bold]")

            if not paths.cloud_env.exists():
                print_error(f"Configuration file not found: {paths.cloud_env}")
                all_valid = False
            else:
                cloud_config = CloudConfig.from_env(paths.cloud_env)
                errors = cloud_config.validate()

                if errors:
                    for error in errors:
                        print_error(error)
                    all_valid = False
                    errors_found.extend(errors)
                else:
                    print_success("Cloud configuration is valid")

        if not all_valid:
            console.print(f"\n[red]Found {len(errors_found)} validation error(s)[/red]")
            ctx.exit(1)
        else:
            console.print("\n[green]All configuration is valid[/green]")

    except RuntimeError as e:
        print_error(str(e))
        ctx.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")
        if ctx.obj.get("verbose"):
            console.print_exception()
        ctx.exit(1)
