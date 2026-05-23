import json
import subprocess
import sys
from pathlib import Path

from passkey.helpers import (
    ACCOUNTS_FILE,
    AGES_DIR,
    PASSKEY_DIR,
    RECIPIENTS_DIR,
    ensure_setup,
    sync_ages_recipients,
)


def _decrypt_file(src: Path, identity: Path) -> str:
    result = subprocess.run(
        ["age", "-d", "-i", str(identity), str(src)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.exit(f"age decrypt failed for {src}: {result.stderr.strip()}")
    return result.stdout


def _parse_passage_content(text: str) -> dict:
    lines = text.splitlines()
    if not lines:
        sys.exit("Decrypted file is empty")
    data = {"password": lines[0]}
    for line in lines[1:]:
        if not line.strip():
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            data[key.strip()] = value.strip()
        else:
            data[line.strip()] = ""
    return data


def _encrypt_payload(payload: str) -> str:
    rfiles = sorted(
        f
        for f in RECIPIENTS_DIR.iterdir()
        if f.is_file() and f.name != ".gitkeep"
    )
    if not rfiles:
        sys.exit(f"No recipient files found in {RECIPIENTS_DIR}")
    age_args = ["age", "-a"]
    for rf in rfiles:
        age_args += ["-R", str(rf)]
    result = subprocess.run(
        age_args, input=payload, capture_output=True, text=True
    )
    if result.returncode != 0:
        sys.exit(f"age encrypt failed: {result.stderr.strip()}")
    return result.stdout


def migrate_from_passage(
    identity: Path, store: Path = Path("~/.passage/store").expanduser()
):
    """Migrate a passage store into the passkey store.

    Decrypts each .age file using identity, parses passage format (first line =
    password, remaining lines = key: value), re-encrypts as passkey JSON, and
    updates accounts.json. Existing accounts with the same name are
    overwritten.
    """
    identity = Path(identity).expanduser()
    store = Path(store).expanduser()

    if not store.exists():
        sys.exit(f"Passage store not found: {store}")
    if not identity.exists():
        sys.exit(f"Identity file not found: {identity}")

    ensure_setup()

    age_files = sorted(store.rglob("*.age"))
    if not age_files:
        sys.exit(f"No .age files found in {store}")

    accounts = json.loads(ACCOUNTS_FILE.read_text())

    for age_file in age_files:
        name = str(age_file.relative_to(store).with_suffix(""))
        print(f"Migrating: {name}")

        data = _parse_passage_content(_decrypt_file(age_file, identity))
        payload = json.dumps(data, indent=2, sort_keys=True)
        ciphertext = _encrypt_payload(payload)

        dest = AGES_DIR / (name.replace("/", "-") + ".age")
        dest.write_text(ciphertext)
        accounts[name] = {"secrets": name}

    tmp = ACCOUNTS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(accounts, indent=2, sort_keys=True))
    tmp.replace(ACCOUNTS_FILE)

    sync_ages_recipients()
    print(f"Migrated {len(age_files)} account(s) to {PASSKEY_DIR}.")
