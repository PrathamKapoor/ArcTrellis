"""Explicit failures for inconsistent static-analysis snapshots."""


class TestAnalysisInvariantError(ValueError):
    """Test derivation inputs do not preserve the established analysis proof."""
