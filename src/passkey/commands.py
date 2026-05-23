import secrets
import string
import sys

from passkey.helpers import (
    build_tree,
    copy_to_clipboard,
    find_matching_accounts,
    format_tree,
    prompt_extra_secret_fields,
    validate_name,
)
from passkey.main import (
    SPECIAL_KEYS,
    decrypt_secrets,
    load_accounts,
    save_accounts,
    secrets_path,
    store_account,
)
from passkey.ui import ui_confirm, ui_password, ui_select, ui_text


def cmd_find(args):
    """Look up an account and reveal a selected secret field."""
    accounts = load_accounts()
    if not accounts:
        sys.exit("No accounts found")

    matches, match_type = find_matching_accounts(args.name, accounts)

    if not matches:
        sys.exit(f"No account matching '{args.name}'")

    if len(matches) == 1:
        chosen = matches[0]
    elif match_type == "group":
        chosen = ui_select(
            f"Accounts in '{args.name}'",
            matches,
            text="Use ↑/↓ to navigate, Enter to confirm.",
        )
    elif match_type == "exact":
        chosen = matches[0]
    else:
        title = f"No exact match for '{args.name}' — did you mean?"
        chosen = ui_select(title, matches)

    account = accounts[chosen]
    secrets_ref = account.get("secrets", chosen)
    data = decrypt_secrets(secrets_path(secrets_ref))

    keys = list(data.keys())
    if "password" in keys:
        keys.remove("password")
        keys.insert(0, "password")
    if not keys:
        sys.exit("Decrypted secrets is empty")
    key = ui_select("Choose secret field", keys)
    value = data[key]

    print(f"Account: {chosen}")
    for k, v in account.items():
        if k in SPECIAL_KEYS:
            continue
        print(f"{k}: {v}")

    if args.print:
        print(f"{key}: {value}")
        return
    clip_tool = copy_to_clipboard(value)
    if clip_tool:
        print(f"({key} copied to clipboard via {clip_tool})")
    else:
        print(f"{key}: {value}")


def cmd_insert(args):
    """Add a new account with a user-typed password."""
    name = args.name
    if not name:
        name = ui_text("Account name", "Enter account name: ")

    validate_name(name)
    accounts = load_accounts()
    if name in accounts:
        sys.exit(
            f"Account '{name}' already exists. Delete it first or pick another name."
        )

    username = ui_text("Username", "Enter username: ")
    password = ui_password("Password", confirm=True)
    data = {"username": username, "password": password}
    data.update(prompt_extra_secret_fields())
    store_account(accounts, name, data)
    print(f"Saved account '{name}'.")


def cmd_generate(args):
    """Add a new account with a randomly generated password."""
    name = args.name
    if not name:
        name = ui_text("Account name", "Enter account name: ")

    validate_name(name)
    accounts = load_accounts()
    if name in accounts:
        sys.exit(
            f"Account '{name}' already exists. Delete it first or pick another name."
        )

    username = ui_text("Username", "Enter username: ")
    alphabet = string.ascii_letters + string.digits
    if not args.no_symbols:
        alphabet += "!@#$%^&*()-_=+[]{};:,.<>?"
    password = "".join(secrets.choice(alphabet) for _ in range(args.length))
    data = {"username": username, "password": password}
    data.update(prompt_extra_secret_fields())
    store_account(accounts, name, data)

    clip_tool = copy_to_clipboard(password)
    if clip_tool:
        print(
            f"Generated password for '{name}' copied to clipboard via {clip_tool}."
        )
    else:
        print(f"Generated password for '{name}': {password}")


def cmd_show(args):
    """Display all accounts in a tree structure."""
    del args
    accounts = load_accounts()
    if not accounts:
        print("No accounts found.")
        return

    tree = build_tree(accounts)
    lines = format_tree(tree)
    for line in lines:
        print(line)


def cmd_remove(args):
    """Remove an account and its encrypted secrets."""
    accounts = load_accounts()
    if not accounts:
        sys.exit("No accounts found")

    matches, match_type = find_matching_accounts(args.name, accounts)

    if not matches:
        sys.exit(f"No account matching '{args.name}'")

    if len(matches) == 1:
        chosen = matches[0]
    elif match_type == "group":
        chosen = ui_select(
            f"Accounts in '{args.name}'",
            matches,
            text="Use ↑/↓ to navigate, Enter to confirm.",
        )
    else:
        title = f"No exact match for '{args.name}' — did you mean?"
        chosen = ui_select(title, matches)

    if not ui_confirm(
        "Remove account", f"Delete '{chosen}'? This cannot be undone."
    ):
        sys.exit("Cancelled")

    secrets_ref = accounts[chosen].get("secrets", chosen)
    secrets_file = secrets_path(secrets_ref)
    if secrets_file.exists():
        secrets_file.unlink()

    del accounts[chosen]
    save_accounts(accounts)
    print(f"Removed account '{chosen}'.")
