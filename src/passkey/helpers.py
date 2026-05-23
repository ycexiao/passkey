import difflib
import re
import shutil
import subprocess
import sys

from passkey.ui import ui_confirm, ui_password, ui_text

SAFE_NAME = re.compile(r"^[A-Za-z0-9._@+\-/]+$")


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
        current = "└── " if is_last_item else "├── "
        lines.append(prefix + current + key + "/")

        extension = "    " if is_last_item else "│   "
        lines.extend(format_tree(tree[key], prefix + extension, is_last_item))

    for i, account in enumerate(accounts):
        is_last_item = i == len(accounts) - 1
        current = "└── " if is_last_item else "├── "
        leaf_name = account.split("/")[-1]
        lines.append(prefix + current + leaf_name)

    return lines
