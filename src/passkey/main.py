#!/usr/bin/env python3
"""passkey - a tiny password manager backed by age.

Storage layout under ~/.passkey:
    accounts.json    unencrypted: hierarchical_name ->
                        { secrets: <path|name>, ...arbitrary }
    identity.txt     age private identity (chmod 600)
    recipients/      one or more files of age public keys
                        (passed to age via -R)
    ages/            encrypted JSON blobs; default key is "password"

Requires: age and age-keygen.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
PASSKEY_DIR = HOME / ".passkey"
ACCOUNTS_FILE = PASSKEY_DIR / "accounts.json"
IDENTITY_FILE = PASSKEY_DIR / "identity.txt"
RECIPIENTS_DIR = PASSKEY_DIR / "recipients"
AGES_DIR = PASSKEY_DIR / "ages"
AGES_RECIPIENTS_DIR = AGES_DIR / "recipients"

SPECIAL_KEYS = {"secrets"}


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


def store_account(accounts, name, secrets_data):
    """Encrypt secrets_data and save both encrypted blob and account
    index."""
    accounts[name] = {
        "secrets": name,
    }
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


def build_parser():
    from passkey.commands import (
        cmd_commit,
        cmd_find,
        cmd_generate,
        cmd_init,
        cmd_insert,
        cmd_remove,
        cmd_rotate,
        cmd_show,
        cmd_sync,
    )

    parser = argparse.ArgumentParser(
        prog="passkey", description="Password manager using age."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    find_parser = sub.add_parser(
        "find",
        help="find an account by name or group and reveal a secret field",
    )
    find_parser.add_argument("name")
    find_parser.add_argument(
        "-p",
        "--print",
        action="store_true",
        help="print the secret instead of copying to clipboard",
    )
    find_parser.set_defaults(func=cmd_find)

    insert_parser = sub.add_parser(
        "insert", help="add a new account with a typed password"
    )
    insert_parser.add_argument(
        "name",
        nargs="?",
        help="hierarchical account name (e.g., Website/Mail/user@example.com)",
    )
    insert_parser.set_defaults(func=cmd_insert)

    generate_parser = sub.add_parser(
        "generate", help="add a new account with a generated password"
    )
    generate_parser.add_argument(
        "name",
        nargs="?",
        help="hierarchical account name (e.g., Website/Mail/user@example.com)",
    )
    generate_parser.add_argument("--length", type=int, default=20)
    generate_parser.add_argument(
        "--no-symbols", action="store_true", help="alphanumeric only"
    )
    generate_parser.set_defaults(func=cmd_generate)

    show_parser = sub.add_parser(
        "show", help="display all accounts in a tree structure"
    )
    show_parser.set_defaults(func=cmd_show)

    remove_parser = sub.add_parser("remove", help="remove an account")
    remove_parser.add_argument(
        "name", help="account name or partial path to search for"
    )
    remove_parser.set_defaults(func=cmd_remove)

    rotate_parser = sub.add_parser(
        "rotate",
        help="re-encrypt secrets when recipients dir has changed",
    )
    rotate_parser.set_defaults(func=cmd_rotate)

    init_parser = sub.add_parser(
        "init",
        help="initialize the ~/.passkey store (aborts if it already exists)",
    )
    init_parser.add_argument(
        "--from",
        dest="from_url",
        metavar="URL",
        help="clone an existing remote git repository as ~/.passkey",
    )
    init_parser.set_defaults(func=cmd_init)

    sync_parser = sub.add_parser(
        "sync",
        help="git pull then git push the ~/.passkey repository",
    )
    sync_parser.set_defaults(func=cmd_sync)

    commit_parser = sub.add_parser(
        "commit",
        help="stage all changes in ~/.passkey and commit",
    )
    commit_parser.add_argument("message", help="commit message")
    commit_parser.set_defaults(func=cmd_commit)

    return parser


def main():
    for binary in ("age", "age-keygen"):
        if not shutil.which(binary):
            sys.exit(
                f"{binary} not found on PATH. Install with: brew install age"
            )
    args = build_parser().parse_args()
    if args.cmd != "init":
        ensure_setup()
    args.func(args)


if __name__ == "__main__":
    main()
