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


def read_text() -> str:
    """Read plain text from the Windows clipboard without opening a window."""
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-Clipboard -Raw",
            ],
            capture_output=True,
            text=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return completed.stdout
