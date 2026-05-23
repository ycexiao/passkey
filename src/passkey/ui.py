import getpass


def ui_select(title, choices, text=""):
    """Show numbered choices and return the selected one.

    Short-circuits and returns immediately when there is only one
    choice.
    """
    if len(choices) == 1:
        return choices[0]

    print(f"\n{title}")
    if text:
        print(text)
    for i, choice in enumerate(choices, 1):
        print(f"  {i}. {choice}")

    while True:
        try:
            idx = int(input("\nChoose (number): ").strip()) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass
        print("Invalid choice. Try again.")


def ui_password(title, confirm=False):
    """Prompt for a hidden password, optionally requiring
    confirmation."""
    while True:
        print(f"\n{title}")
        pw = getpass.getpass("Enter password: ")
        if not confirm:
            return pw
        again = getpass.getpass("Re-enter password: ")
        if pw == again:
            return pw
        print("Passwords do not match. Try again.")


def ui_text(title, prompt_text):
    """Show a plain text input and return what the user typed."""
    print(f"\n{title}")
    return input(prompt_text).strip()


def ui_confirm(title, text):
    """Show a yes/no prompt and return the user's choice."""
    print(f"\n{title}")
    print(text)
    while True:
        resp = input("(y/n): ").strip().lower()
        if resp in ("y", "yes"):
            return True
        if resp in ("n", "no"):
            return False
        print("Please enter 'y' or 'n'.")
