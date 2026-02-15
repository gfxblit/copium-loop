"""Copium Loop - AI-powered development workflow automation."""

from copium_loop.patches import patch_all

patch_all()

from copium_loop.copium_loop import WorkflowManager  # noqa: E402

__version__ = "0.1.0"

__all__ = ["WorkflowManager"]
