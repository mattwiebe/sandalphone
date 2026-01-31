"""Output formatting utilities."""

import json
from typing import Any, Dict, List

from rich.console import Console
from rich.table import Table


console = Console()


def format_table(
    data: List[Dict[str, Any]], title: str = "", columns: List[tuple[str, str]] = None
) -> Table:
    """
    Format data as a rich table.

    Args:
        data: List of dictionaries containing row data
        title: Optional table title
        columns: List of (column_name, style) tuples. If None, uses data keys.

    Returns:
        Rich Table object
    """
    table = Table(title=title, show_header=True, header_style="bold cyan")

    if not data:
        return table

    # Determine columns from data if not provided
    if columns is None:
        columns = [(key, "") for key in data[0].keys()]

    # Add columns
    for col_name, style in columns:
        table.add_column(col_name, style=style)

    # Add rows
    for row in data:
        values = []
        for col_name, _ in columns:
            value = row.get(col_name, "")
            # Handle color markup
            if isinstance(value, tuple):
                # (value, color) tuple
                text, color = value
                values.append(f"[{color}]{text}[/{color}]")
            else:
                values.append(str(value))
        table.add_row(*values)

    return table


def print_table(
    data: List[Dict[str, Any]], title: str = "", columns: List[tuple[str, str]] = None
):
    """
    Print data as a rich table to console.

    Args:
        data: List of dictionaries containing row data
        title: Optional table title
        columns: List of (column_name, style) tuples
    """
    table = format_table(data, title, columns)
    console.print(table)


def print_json(data: Any, pretty: bool = True):
    """
    Print data as JSON.

    Args:
        data: Data to serialize
        pretty: Whether to pretty-print with indentation
    """
    if pretty:
        print(json.dumps(data, indent=2, default=str))
    else:
        print(json.dumps(data, default=str))


def print_error(message: str):
    """
    Print an error message in red.

    Args:
        message: Error message
    """
    console.print(f"[red]Error:[/red] {message}")


def print_success(message: str):
    """
    Print a success message in green.

    Args:
        message: Success message
    """
    console.print(f"[green]✓[/green] {message}")


def print_warning(message: str):
    """
    Print a warning message in yellow.

    Args:
        message: Warning message
    """
    console.print(f"[yellow]⚠[/yellow] {message}")


def print_info(message: str):
    """
    Print an info message in blue.

    Args:
        message: Info message
    """
    console.print(f"[blue]ℹ[/blue] {message}")


def print_key_value(key: str, value: Any, redacted: bool = False):
    """
    Print a key-value pair.

    Args:
        key: Key name
        value: Value
        redacted: Whether to redact the value
    """
    if redacted:
        value_str = "********"
    else:
        value_str = str(value)

    console.print(f"[cyan]{key}:[/cyan] {value_str}")
