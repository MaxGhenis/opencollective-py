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
@click.argument("receipt", type=click.Path(exists=True), required=False)
@click.option(
    "-c", "--collective", required=True, help="Collective slug (e.g., policyengine)"
)
@click.option("-t", "--tag", multiple=True, help="Tags for the expense")
@click.option("--currency", help="Currency code (e.g., GBP). Defaults to collective's.")
@click.option("--incurred-at", help="Date incurred (YYYY-MM-DD). Defaults to today.")
@click.option("-i", "--item", multiple=True,
              help='Multi-item: pass multiple times as "description|amount|receipt_file|YYYY-MM-DD"')
@handle_errors
def reimbursement(description: str, amount: float, receipt: str | None,
                  collective: str, tag, currency: str | None,
                  incurred_at: str | None, item):
    """Submit a reimbursement expense with one or more receipts.

    Single-item:
        oc reimbursement "NASI Dues 2026" 325.00 receipt.pdf -c policyengine

    Multi-item (each -i is "desc|amount|file|date"):
        oc reimbursement "Travel April 2026" 0 -c policyengine \\
          -i "Flight|450|flight.pdf|2026-04-01" \\
          -i "Hotel|320|hotel.pdf|2026-04-02"
    """
    client = get_client()
    tags = list(tag) if tag else None

    if item:
        # Multi-item mode
        items = []
        for spec in item:
            parts = spec.split("|")
            if len(parts) < 3:
                raise click.ClickException(
                    f"--item must be 'desc|amount|receipt' or 'desc|amount|receipt|date'; got: {spec}"
                )
            items.append({
                "description": parts[0],
                "amount_cents": int(float(parts[1]) * 100),
                "receipt_file": parts[2],
                "incurred_at": parts[3] if len(parts) > 3 else incurred_at,
            })
        total = sum(i["amount_cents"] for i in items) / 100
        click.echo(f"Submitting multi-item reimbursement for ${total:.2f} ({len(items)} items)...")
        expense = client.submit_multi_item_reimbursement(
            collective_slug=collective,
            description=description,
            items=items,
            tags=tags,
            currency=currency,
        )
    else:
        if not receipt:
            raise click.ClickException("RECEIPT arg required when --item is not used")
        amount_cents = int(amount * 100)
        click.echo(f"Submitting reimbursement for ${amount:.2f}...")
        expense = client.submit_reimbursement(
            collective_slug=collective,
            description=description,
            amount_cents=amount_cents,
            receipt_file=receipt,
            tags=tags,
            currency=currency,
            incurred_at=incurred_at,
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
@click.option("--json", "as_json", is_flag=True, help="Output as JSON for scripting")
@handle_errors
def expenses(collective: str, pending: bool, mine: bool, limit: int, as_json: bool):
    """List expenses for a collective.

    Example:
        oc expenses -c policyengine --pending
        oc expenses -c policyengine --mine --json | jq ...
    """
    client = get_client()

    status_filter = "PENDING" if pending else None
    result = client.get_expenses(collective, status=status_filter, limit=limit)
    nodes = result.get("nodes", [])

    if mine:
        me = client.get_me()
        my_slug = me.get("slug")
        nodes = [e for e in nodes if e.get("payee", {}).get("slug") == my_slug]

    if as_json:
        click.echo(json.dumps(nodes, indent=2, default=str))
        return

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
        currency = exp.get("currency", "USD")
        status = exp.get("status", "UNKNOWN")
        desc = exp.get("description", "No description")
        legacy_id = exp.get("legacyId", "?")
        payee = exp.get("payee", {}).get("name", "Unknown")
        icon = status_icons.get(status, "?")

        click.echo(f"  {icon} #{legacy_id} {currency} {amount:,.2f} - {desc}")
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
@click.argument("expense_id", required=False)
@click.option("-c", "--collective", help="Collective slug (required with --all-mine)")
@click.option("--all-mine", is_flag=True,
              help="Approve all PENDING expenses payable to me")
@handle_errors
def approve(expense_id: str | None, collective: str | None, all_mine: bool):
    """Approve a pending expense (requires admin permissions).

    Single:
        oc approve abc123-def456

    Bulk approve all your pending:
        oc approve --all-mine -c policyengine
    """
    client = get_client()
    if all_mine:
        if not collective:
            raise click.ClickException("--all-mine requires -c/--collective")
        me = client.get_me()
        my_slug = me["slug"]
        result = client.get_expenses(collective, status="PENDING", limit=100)
        mine = [e for e in result.get("nodes", []) if e.get("payee", {}).get("slug") == my_slug]
        click.echo(f"Found {len(mine)} PENDING expense(s) payable to @{my_slug}")
        ok, fail = 0, 0
        for exp in mine:
            try:
                client.approve_expense(exp["legacyId"])
                click.echo(f"  \u2713 #{exp['legacyId']}: {exp['description'][:70]}")
                ok += 1
            except Exception as e:
                click.echo(f"  \u2717 #{exp['legacyId']}: {e}", err=True)
                fail += 1
        click.echo(f"\nApproved {ok}, failed {fail}.")
        return

    if not expense_id:
        raise click.ClickException("EXPENSE_ID required (or use --all-mine)")
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
@click.argument("personal_token", required=False)
@handle_errors
def login(personal_token: str | None):
    """Save a Personal Token (easiest auth — recommended).

    Create one at https://opencollective.com/applications (Personal Tokens tab,
    "expenses" scope). Then either:

        oc login abc123deadbeef...      # inline
        oc login                        # interactive prompt
    """
    if not personal_token:
        personal_token = click.prompt(
            "Paste Personal Token (from opencollective.com/applications)",
            hide_input=True,
        ).strip()

    if not (len(personal_token) == 40 and all(c in "0123456789abcdef" for c in personal_token)):
        click.echo(
            "\u26a0  Token doesn't look like a 40-char hex Personal Token.\n"
            "   Saving anyway, but you may need 'oc auth' if it's an OAuth JWT.",
            err=True,
        )

    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump({"access_token": personal_token, "token_type": "PersonalToken"}, f)
    os.chmod(TOKEN_FILE, 0o600)

    client = OpenCollectiveClient(access_token=personal_token)
    me_data = client.get_me()
    click.echo(f"\u2713 Saved to {TOKEN_FILE}")
    click.echo(f"  Logged in as: {me_data.get('name')} (@{me_data.get('slug')})")


@cli.command()
@click.option("--client-id", prompt=True, help="OAuth2 client ID")
@click.option("--client-secret", prompt=True, hide_input=True, help="OAuth2 secret")
@handle_errors
def auth(client_id: str, client_secret: str):
    """Authenticate with OpenCollective OAuth2 (for app integrations).

    For personal use, prefer 'oc login' with a Personal Token instead.
    Get OAuth credentials at https://opencollective.com/applications.
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
