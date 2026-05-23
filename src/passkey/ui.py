import os
import sys

from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.styles import Style
from prompt_toolkit.validation import ValidationError, Validator

_USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
_CYAN_BOLD = "\033[1;36m"
_RESET = "\033[0m"

_STYLE = (
    Style.from_dict({"validation-toolbar": "bg:#aa0000 #ffffff bold"})
    if _USE_COLOR
    else None
)


def _styled_prompt(text):
    return ANSI(f"{_CYAN_BOLD}{text}{_RESET}") if _USE_COLOR else text


class _ChoiceValidator(Validator):
    def __init__(self, choices):
        self._choices = choices

    def validate(self, document):
        if document.text not in self._choices:
            raise ValidationError(
                message="Not a valid choice — Tab to see options",
                cursor_position=len(document.text),
            )


class _YesNoValidator(Validator):
    def validate(self, document):
        if document.text and document.text.lower() not in (
            "y",
            "yes",
            "n",
            "no",
        ):
            raise ValidationError(
                message="Enter 'y' or 'n'",
                cursor_position=len(document.text),
            )


def ui_select(title, choices, text=""):
    """Inline fuzzy-complete selector; short-circuits on a single
    choice."""
    if len(choices) == 1:
        return choices[0]

    if text:
        print(text)

    completer = WordCompleter(choices, ignore_case=True, match_middle=True)
    return prompt(
        _styled_prompt("Choose (Tab to complete): "),
        completer=completer,
        validator=_ChoiceValidator(choices),
        validate_while_typing=False,
        complete_while_typing=True,
        style=_STYLE,
    )


def ui_password(title, confirm=False):
    """Masked password prompt, optionally requiring confirmation."""
    while True:
        pw = prompt(
            _styled_prompt("Enter password: "), is_password=True, style=_STYLE
        )
        if not confirm:
            return pw
        again = prompt(
            _styled_prompt("Re-enter password: "),
            is_password=True,
            style=_STYLE,
        )
        if pw == again:
            return pw
        print("Passwords do not match. Try again.")


def ui_text(title, prompt_text, default=""):
    """Single-line text prompt."""
    display = f"{prompt_text} ({default}): " if default else prompt_text
    result = prompt(_styled_prompt(display)).strip()
    return result if result else default


def ui_confirm(title, text, default="n"):
    """Inline yes/no prompt with validation."""
    resp = (
        prompt(
            _styled_prompt(f"{text} ({default}): "),
            validator=_YesNoValidator(),
            validate_while_typing=False,
            style=_STYLE,
        )
        .strip()
        .lower()
    )
    return (resp if resp else default) in ("y", "yes")
