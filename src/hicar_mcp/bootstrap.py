"""Choose live vs bundled knowledge based on the discovered config."""

from __future__ import annotations

from .artifacts.loader import ArtifactsUnavailable, load_bundled
from .config import Config
from .extract.runner import extract_from_repo
from .kb import Knowledge


def load_knowledge(config: Config) -> Knowledge:
    """Build the knowledge base.

    Live mode (HICAR_REPO set) parses the checkout so working-tree changes are
    reflected; if that fails for any reason we fall back to bundled artifacts.
    """
    if config.mode == "live" and config.repo_root is not None:
        try:
            return extract_from_repo(config.repo_root, mode="live")
        except (OSError, ValueError):
            pass  # fall back to bundled
    return load_bundled(config.data_dir)
