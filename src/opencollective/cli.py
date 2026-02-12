"""OpenCollective CLI."""

import functools
import json
import os
import sys

import click

from .client import OpenCollectiveClient

TOKEN_FILE = os.path.expanduser("~/.config/opencollective/token.json")


def get_client() -> OpenCollectiveClient:
    """Get an authenticated client from saved token."""
    if not os.path.exists(TOKEN_FILE):
        click.echo(f"Error: No token found at {TOKEN_FILE}", err=True)
        click.echo("Run 'oc auth' to authenticate first.", err=True)
        sys.exit(1)

    with open(TOKEN_FILE) as f:
        token_data = json.load(f)

    return OpenCollectiveClient(access_token=token_data["access_token"])


def handle_errors(func):
    """Decorator that catches exceptions and exits with an error message."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)

    return wrapper


def _echo_expense_created(collective: str, expense: dict) -> None:
    """Print success message after creating an expense."""
    legacy_id = expense["legacyId"]
    click.echo(f"\u2713 Created expense #{legacy_id}")
    click.echo(f"  View: https://opencollective.com/{collective}/expenses/{legacy_id}")


@click.group()
@click.version_option()
def cli():
    """OpenCollective CLI - manage expenses from the command line."""
    pass


@cli.command()
@click.argument("description")
@click.argument("amount", type=float)
@click.argument("receipt", type=click.Path(exists=True))
@click.option(
    "-c", "--collective", required=True, help="Collective slug (e.g., policyengine)"
)
@click.option("-t", "--tag", multiple=True, help="Tags for the expense")
@handle_errors
def reimbursement(description: str, amount: float, receipt: str, collective: str, tag):
    """Submit a reimbursement expense with a receipt.

    Example:
        oc reimbursement "NASI Dues 2026" 325.00 receipt.pdf -c policyengine
    """
    client = get_client()
    amount_cents = int(amount * 100)
    tags = list(tag) if tag else None

    click.echo(f"Submitting reimbursement for ${amount:.2f}...")

    expense = client.submit_reimbursement(
        collective_slug=collective,
        description=description,
        amount_cents=amount_cents,
        receipt_file=receipt,
        tags=tags,
    )
    _echo_expense_created(collective, expense)


@cli.command()
@click.argument("description")
@click.argument("amount", type=float)
@click.option(
    "-c", "--collective", required=True, help="Collective slug (e.g., policyengine)"
)
@click.option("-i", "--invoice", type=click.Path(exists=True), help="Invoice file")
@click.option("-t", "--tag", multiple=True, help="Tags for the expense")
@handle_errors
def invoice(description: str, amount: float, collective: str, invoice: str | None, tag):
    """Submit an invoice expense.

    Example:
        oc invoice "January Consulting" 5000.00 -c policyengine
    """
    client = get_client()
    amount_cents = int(amount * 100)
    tags = list(tag) if tag else None

    click.echo(f"Submitting invoice for ${amount:.2f}...")

    expense = client.submit_invoice(
        collective_slug=collective,
        description=description,
        amount_cents=amount_cents,
        invoice_file=invoice,
        tags=tags,
    )
    _echo_expense_created(collective, expense)


@cli.command()
@click.option(
    "-c", "--collective", required=True, help="Collective slug (e.g., policyengine)"
)
@click.option("--pending", is_flag=True, help="Show only pending expenses")
@click.option("--mine", is_flag=True, help="Show only my expenses")
@click.option("-n", "--limit", default=20, help="Number of expenses to show")
@handle_errors
def expenses(collective: str, pending: bool, mine: bool, limit: int):
    """List expenses for a collective.

    Example:
        oc expenses -c policyengine --pending
    """
    client = get_client()

    status_filter = "PENDING" if pending else None
    result = client.get_expenses(collective, status=status_filter, limit=limit)
    nodes = result.get("nodes", [])

    if mine:
        me = client.get_me()
        my_slug = me.get("slug")
        nodes = [e for e in nodes if e.get("payee", {}).get("slug") == my_slug]

    if not nodes:
        click.echo("No expenses found.")
        return

    status_icons = {
        "PENDING": "\u23f3",
        "APPROVED": "\u2713",
        "PAID": "\U0001f4b0",
        "REJECTED": "\u2717",
    }

    click.echo(f"Found {len(nodes)} expense(s):\n")
    for exp in nodes:
        amount = exp.get("amount", 0) / 100
        status = exp.get("status", "UNKNOWN")
        desc = exp.get("description", "No description")
        legacy_id = exp.get("legacyId", "?")
        payee = exp.get("payee", {}).get("name", "Unknown")
        icon = status_icons.get(status, "?")

        click.echo(f"  {icon} #{legacy_id} ${amount:.2f} - {desc}")
        click.echo(f"     Payee: {payee} | Status: {status}")
        click.echo()


@cli.command()
@click.argument("expense_id")
@handle_errors
def delete(expense_id: str):
    """Delete an expense (draft/pending only).

    Example:
        oc delete abc123-def456
    """
    client = get_client()
    result = client.delete_expense(expense_id)
    click.echo(f"\u2713 Deleted expense #{result.get('legacyId')}")


@cli.command()
@click.argument("expense_id")
@handle_errors
def approve(expense_id: str):
    """Approve a pending expense (requires admin permissions).

    Example:
        oc approve abc123-def456
    """
    client = get_client()
    result = client.approve_expense(expense_id)
    click.echo(f"\u2713 Approved expense #{result.get('legacyId')}")
    click.echo(f"  Status: {result.get('status')}")


@cli.command()
@click.argument("expense_id")
@click.option("-m", "--message", help="Rejection message")
@handle_errors
def reject(expense_id: str, message: str | None):
    """Reject a pending expense (requires admin permissions).

    Example:
        oc reject abc123-def456 -m "Missing receipt"
    """
    client = get_client()
    result = client.reject_expense(expense_id, message=message)
    click.echo(f"\u2713 Rejected expense #{result.get('legacyId')}")
    click.echo(f"  Status: {result.get('status')}")


@cli.command()
@handle_errors
def me():
    """Show current authenticated user."""
    client = get_client()
    me_data = client.get_me()
    click.echo(f"Logged in as: {me_data.get('name')} (@{me_data.get('slug')})")

    methods = client.get_payout_methods(me_data["slug"])
    if methods:
        click.echo("\nPayout methods:")
        for m in methods:
            click.echo(f"  - {m['type']}: {m['id']}")


@cli.command()
@click.option("--client-id", prompt=True, help="OAuth2 client ID")
@click.option("--client-secret", prompt=True, hide_input=True, help="OAuth2 secret")
@handle_errors
def auth(client_id: str, client_secret: str):
    """Authenticate with OpenCollective OAuth2.

    Get credentials at: https://opencollective.com/applications
    """
    from .auth import OAuth2Handler

    handler = OAuth2Handler(
        client_id=client_id,
        client_secret=client_secret,
        token_file=TOKEN_FILE,
    )

    auth_url = handler.get_authorization_url(scope="expenses")
    click.echo(f"\nOpen this URL in your browser:\n\n{auth_url}\n")

    code = click.prompt("Paste the authorization code")

    token_data = handler.exchange_code(code)
    click.echo("\n\u2713 Authenticated successfully!")
    click.echo(f"  Token saved to: {TOKEN_FILE}")

    client = OpenCollectiveClient(access_token=token_data["access_token"])
    me_data = client.get_me()
    click.echo(f"  Logged in as: {me_data.get('name')} (@{me_data.get('slug')})")


if __name__ == "__main__":
    cli()
