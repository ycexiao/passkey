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
import shutil
import sys

from passkey.helpers import ensure_setup


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
