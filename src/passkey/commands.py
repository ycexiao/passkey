import json
import secrets
import string
import subprocess
import sys

from passkey.helpers import (
    ACCOUNTS_FILE,
    AGES_DIR,
    AGES_RECIPIENTS_DIR,
    PASSKEY_DIR,
    RECIPIENTS_DIR,
    SPECIAL_KEYS,
    _setup_identity,
    build_tree,
    copy_to_clipboard,
    decrypt_secrets,
    find_matching_accounts,
    format_tree,
    load_accounts,
    prompt_extra_secret_fields,
    save_accounts,
    secrets_path,
    store_account,
    sync_ages_recipients,
    validate_name,
)
from passkey.ui import ui_confirm, ui_password, ui_select, ui_text


def cmd_init(args):
    """Initialize the ~/.passkey store, optionally cloning from a
    remote."""
    if PASSKEY_DIR.exists() and any(PASSKEY_DIR.iterdir()):
        sys.exit(
            f"{PASSKEY_DIR} already exists and is not empty. Remove it first."
        )

    if args.from_url:
        result = subprocess.run(
            ["git", "clone", args.from_url, str(PASSKEY_DIR)]
        )
        if result.returncode != 0:
            sys.exit("git clone failed.")
        for d in [RECIPIENTS_DIR, AGES_DIR, AGES_RECIPIENTS_DIR]:
            d.mkdir(parents=True, exist_ok=True)
        if not ACCOUNTS_FILE.exists():
            save_accounts({})
    else:
        PASSKEY_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "-C", str(PASSKEY_DIR), "init"], check=True)
        (PASSKEY_DIR / ".gitignore").write_text("identity.txt\n")
        for d in [RECIPIENTS_DIR, AGES_DIR, AGES_RECIPIENTS_DIR]:
            d.mkdir(parents=True, exist_ok=True)
            (d / ".gitkeep").touch()
        save_accounts({})

    _setup_identity()
    print(f"Passkey store initialized at {PASSKEY_DIR}.")


def cmd_sync(args):
    """Pull then push the ~/.passkey git repository."""
    del args
    for git_cmd in [["pull"], ["push"]]:
        result = subprocess.run(["git", "-C", str(PASSKEY_DIR)] + git_cmd)
        if result.returncode != 0:
            sys.exit(f"git {git_cmd[0]} failed.")


def cmd_commit(args):
    """Stage all changes in ~/.passkey and commit with the given
    message."""
    subprocess.run(["git", "-C", str(PASSKEY_DIR), "add", "-A"], check=True)
    result = subprocess.run(
        ["git", "-C", str(PASSKEY_DIR), "commit", "-m", args.message]
    )
    if result.returncode != 0:
        sys.exit("git commit failed.")


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


def prompt_extra_non_secret_fields():
    """Interactively collect additional non-secret key/value pairs."""
    fields = {}
    while ui_confirm("Extra fields", "Add another non-secret field?"):
        key = ui_text("Field name", "Name of the field:").strip()
        if not key:
            continue
        fields[key] = ui_text(
            f"Value for '{key}'", f"Enter value for '{key}': "
        )
    return fields


def cmd_insert(args):
    """Add a new account with a user-typed password."""
    accounts = load_accounts()
    name = args.name
    if not name:
        folders = sorted({n.split("/")[0] for n in accounts if "/" in n})
        hint = f" [{', '.join(folders)}]" if folders else ""
        name = ui_text("Account name", f"Enter account name{hint}: ")

    validate_name(name)
    if name in accounts:
        sys.exit(
            f"Account '{name}' already exists. "
            "Delete it first or pick another name."
        )

    username = ui_text("Username", "Enter username", default="NAN")
    meta = {"username": username}
    meta.update(prompt_extra_non_secret_fields())

    password = ui_password("Password", confirm=True)
    secret = {"password": password}
    secret.update(prompt_extra_secret_fields())

    store_account(accounts, name, secret, meta=meta)
    print(f"Saved account '{name}'.")


def cmd_generate(args):
    """Add a new account with a randomly generated password."""
    accounts = load_accounts()
    name = args.name
    if not name:
        folders = sorted({n.split("/")[0] for n in accounts if "/" in n})
        hint = f" [{', '.join(folders)}]" if folders else ""
        name = ui_text("Account name", f"Enter account name{hint}: ")

    validate_name(name)
    if name in accounts:
        sys.exit(
            f"Account '{name}' already exists. "
            "Delete it first or pick another name."
        )

    username = ui_text("Username", "Enter username", default="NAN")
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
            f"Generated password for '{name}' copied to "
            f"clipboard via {clip_tool}."
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


def cmd_rotate(args):
    """Re-encrypt secrets whose recipients dir has diverged from the
    global recipients dir."""
    del args

    def _itered_dir(d):
        return (
            {f.name: f.read_text().strip() for f in d.iterdir() if f.is_file()}
            if d.exists()
            else {}
        )

    desired = _itered_dir(RECIPIENTS_DIR)
    current = _itered_dir(AGES_RECIPIENTS_DIR)

    if desired == current:
        print("Recipients unchanged. Nothing to do.")
        return

    added = {n for n, t in desired.items() if current.get(n) != t}
    removed = {
        n for n in current if n not in desired or current[n] != desired[n]
    }
    print("\nRecipient changes detected:")
    for n in sorted(added - removed):
        print(f"  + {n}")
    for n in sorted(removed - added):
        print(f"  - {n}")
    for n in sorted(added & removed):
        print(f"  ~ {n}")

    accounts = load_accounts()
    age_files = []
    for name, account in accounts.items():
        ref = account.get("secrets", name)
        p = secrets_path(ref)
        if p.exists():
            age_files.append((name, p))

    if age_files:
        print(f"\nWill re-encrypt {len(age_files)} file(s):")
        for _, p in age_files:
            print(f"  {p.name}")
    else:
        print("\nNo encrypted files to rotate.")
        sync_ages_recipients()
        return

    if not ui_confirm("Rotate recipients", "Proceed with rotation?"):
        sys.exit("Cancelled.")

    rfiles = sorted(f for f in RECIPIENTS_DIR.iterdir() if f.is_file())
    if not rfiles:
        sys.exit(f"No recipient files found in {RECIPIENTS_DIR}")
    age_args = ["age", "-a"]
    for rf in rfiles:
        age_args += ["-R", str(rf)]

    for _, src in age_files:
        data = decrypt_secrets(src)
        payload = json.dumps(data, indent=2, sort_keys=True)
        result = subprocess.run(
            age_args, input=payload, capture_output=True, text=True
        )
        if result.returncode != 0:
            sys.exit(
                f"age encrypt failed for {src.name}: {result.stderr.strip()}"
            )
        src.write_text(result.stdout)
        print(f"  Rotated: {src.name}")

    sync_ages_recipients()
    print("\nRotation complete.")
