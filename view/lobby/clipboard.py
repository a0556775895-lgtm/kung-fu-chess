"""Windows clipboard integration for sharing a created room code."""

import subprocess


def copy_text(text: str) -> None:
    """Copy text through the built-in Windows clip command without a shell."""
    subprocess.run(
        ["clip"],
        input=text,
        text=True,
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
