import difflib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from passkey.ui import ui_confirm, ui_password, ui_text

HOME = Path.home()
PASSKEY_DIR = HOME / ".passkey"
ACCOUNTS_FILE = PASSKEY_DIR / "accounts.json"
IDENTITY_FILE = PASSKEY_DIR / "identity.txt"
RECIPIENTS_DIR = PASSKEY_DIR / "recipients"
AGES_DIR = PASSKEY_DIR / "ages"
AGES_RECIPIENTS_DIR = AGES_DIR / "recipients"

SPECIAL_KEYS = {"secrets"}

_USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

_DIM = "\033[2m"
_CYAN_BOLD = "\033[1;36m"
_GREEN = "\033[32m"
_RESET = "\033[0m"


def _dim(s):
    return f"{_DIM}{s}{_RESET}" if _USE_COLOR else s


def _group(s):
    return f"{_CYAN_BOLD}{s}{_RESET}" if _USE_COLOR else s


def _leaf(s):
    return f"{_GREEN}{s}{_RESET}" if _USE_COLOR else s


SAFE_NAME = re.compile(r"^[A-Za-z0-9._@+\-/]+$")


def _setup_identity():
    """Generate identity.txt if absent and register its public key in
    recipients/."""
    if not IDENTITY_FILE.exists():
        subprocess.run(
            ["age-keygen", "-o", str(IDENTITY_FILE)],
            capture_output=True,
            text=True,
            check=True,
        )
        IDENTITY_FILE.chmod(0o600)
        print(f"Generated identity at {IDENTITY_FILE}.", file=sys.stderr)

    pubkey = subprocess.run(
        ["age-keygen", "-y", str(IDENTITY_FILE)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if pubkey:
        existing = [
            f
            for f in RECIPIENTS_DIR.iterdir()
            if f.is_file() and f.name != ".gitkeep"
        ]
        if not any(pubkey in f.read_text() for f in existing):
            dest = RECIPIENTS_DIR / "default.txt"
            i = 1
            while dest.exists():
                dest = RECIPIENTS_DIR / f"default-{i}.txt"
                i += 1
            dest.write_text(pubkey + "\n")
            print(f"Public key written to {dest}.", file=sys.stderr)


def ensure_setup():
    """Exit with a helpful error if the passkey store is not
    initialized."""
    missing = [
        str(p)
        for p in [
            PASSKEY_DIR,
            RECIPIENTS_DIR,
            AGES_DIR,
            AGES_RECIPIENTS_DIR,
            ACCOUNTS_FILE,
            IDENTITY_FILE,
        ]
        if not p.exists()
    ]
    if missing:
        sys.exit(
            "Passkey store is not initialized. Run: passkey init\n"
            "Missing: " + ", ".join(missing)
        )


def load_accounts():
    """Read accounts.json and return the full accounts dict."""
    return json.loads(ACCOUNTS_FILE.read_text())


def save_accounts(accounts):
    """Atomically write the accounts dict to disk via a tmp file."""
    tmp = ACCOUNTS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(accounts, indent=2, sort_keys=True))
    tmp.replace(ACCOUNTS_FILE)


def secrets_path(ref):
    """Resolve a secrets reference to the Path of its .age file."""
    p = Path(ref)
    if p.is_absolute():
        return p
    # Replace / with - in the filename to avoid creating subdirectories.
    fname = ref.replace("/", "-") if not ref.endswith(".age") else ref
    if not fname.endswith(".age"):
        fname += ".age"
    return AGES_DIR / fname


def decrypt_secrets(src):
    """Decrypt an age-encrypted JSON blob and return its contents as a
    dict."""
    if not src.exists():
        sys.exit(f"No encrypted file at: {src}")
    result = subprocess.run(
        ["age", "-d", "-i", str(IDENTITY_FILE), str(src)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.exit(f"age decrypt failed: {result.stderr.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        sys.exit(f"Decrypted contents of {src} is not valid JSON")


def sync_ages_recipients():
    """Copy RECIPIENTS_DIR contents into AGES_RECIPIENTS_DIR, replacing
    existing files."""
    for f in AGES_RECIPIENTS_DIR.iterdir():
        if f.is_file():
            f.unlink()
    for f in sorted(RECIPIENTS_DIR.iterdir()):
        if f.is_file():
            (AGES_RECIPIENTS_DIR / f.name).write_text(f.read_text())


def store_account(accounts, name, secrets_data, meta=None):
    """Encrypt secrets_data and save both encrypted blob and account
    index."""
    entry = {"secrets": name}
    if meta:
        entry.update(meta)
    accounts[name] = entry
    dest = secrets_path(name)
    rfiles = [f for f in sorted(RECIPIENTS_DIR.iterdir()) if f.is_file()]
    if not rfiles:
        sys.exit(f"No recipient files found in {RECIPIENTS_DIR}")
    age_args = ["age", "-a"]
    for rf in rfiles:
        age_args += ["-R", str(rf)]
    payload = json.dumps(secrets_data, indent=2, sort_keys=True)
    result = subprocess.run(
        age_args, input=payload, capture_output=True, text=True
    )
    if result.returncode != 0:
        sys.exit(f"age encrypt failed: {result.stderr.strip()}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(result.stdout)
    save_accounts(accounts)
    sync_ages_recipients()


def copy_to_clipboard(text):
    """Copy text to the system clipboard using the first available
    tool."""
    if shutil.which("pbcopy"):
        subprocess.run(["pbcopy"], input=text, text=True, check=True)
        return "pbcopy"
    if shutil.which("wl-copy"):
        subprocess.run(["wl-copy"], input=text, text=True, check=True)
        return "wl-copy"
    if shutil.which("xclip"):
        subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=text,
            text=True,
            check=True,
        )
        return "xclip"
    return None


def validate_name(name):
    if not SAFE_NAME.match(name) or name.startswith("/") or name.endswith("/"):
        sys.exit(
            f"Invalid account name: {name!r}. Allowed: letters, "
            "digits, . _ @ + - /. Format: Category/Subcategory/name"
        )


def prompt_extra_secret_fields():
    """Interactively collect additional secret key/value pairs beyond
    password."""
    fields = {}
    while ui_confirm("Extra fields", "Add another secret field?"):
        key = ui_text("Field name", "Name of the field:").strip()
        if not key:
            continue
        fields[key] = ui_password(f"Value for '{key}'")
    return fields


def find_matching_accounts(query, accounts):
    """Find matching accounts by exact, substring, group, or fuzzy
    matching."""
    if query in accounts:
        return [query], "exact"

    group_matches = [n for n in accounts if n.startswith(query + "/")]
    if group_matches:
        return sorted(group_matches), "group"

    substring = [n for n in accounts if query.lower() in n.lower()]
    if substring:
        return sorted(substring), "substring"

    fuzzy = difflib.get_close_matches(
        query, list(accounts.keys()), n=10, cutoff=0.3
    )
    if fuzzy:
        return fuzzy, "fuzzy"

    return [], "none"


def build_tree(accounts):
    """Build a tree structure from hierarchical account names."""
    tree = {"__accounts__": []}
    for name in sorted(accounts.keys()):
        parts = name.split("/")
        current = tree
        for part in parts[:-1]:
            if part not in current:
                current[part] = {"__accounts__": []}
            current = current[part]
        current["__accounts__"].append(name)
    return tree


def format_tree(tree, prefix="", is_last=True):
    """Format tree for display using box-drawing characters."""
    del is_last
    lines = []
    items = sorted([k for k in tree.keys() if k != "__accounts__"])
    accounts = tree.get("__accounts__", [])

    for i, key in enumerate(items):
        is_last_item = (i == len(items) - 1) and not accounts
        connector = "└── " if is_last_item else "├── "
        lines.append(prefix + _dim(connector) + _group(key + "/"))

        extension = "    " if is_last_item else "│   "
        lines.extend(
            format_tree(
                tree[key],
                prefix + _dim(extension) if _USE_COLOR else prefix + extension,
                is_last_item,
            )
        )

    for i, account in enumerate(accounts):
        is_last_item = i == len(accounts) - 1
        connector = "└── " if is_last_item else "├── "
        leaf_name = account.split("/")[-1]
        lines.append(prefix + _dim(connector) + _leaf(leaf_name))

    return lines
