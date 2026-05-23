"""Unit tests for __version__.py."""

import passkey  # noqa


def test_package_version():
    """Ensure the package version is defined and not set to the initial
    placeholder."""
    assert hasattr(passkey, "__version__")
    assert passkey.__version__ != "0.0.0"
