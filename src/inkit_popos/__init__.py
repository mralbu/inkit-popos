"""inkit-popos: voice dictation for Pop!_OS / COSMIC (Wayland).

A backend-agnostic dictation daemon inspired by Cartesia's macOS InkIt app.
Capture audio -> transcribe (Cartesia API or local Parakeet) -> optional LLM
polish -> type the text at the cursor.
"""

__version__ = "0.1.0"
