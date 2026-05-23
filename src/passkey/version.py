#!/usr/bin/env python
##############################################################################
#
# (c) 2026 BSD-3.
# All rights reserved.
#
# File coded by: Yuchen Xiao.
#
# See GitHub contributions for a more detailed list of contributors.
# https://github.com/ycexiao/passkey/graphs/contributors  # noqa: E501
#
# See LICENSE.rst for license information.
#
##############################################################################
"""Definition of __version__."""

#  We do not use the other three variables, but can be added back if needed.
#  __all__ = ["__date__", "__git_commit__", "__timestamp__", "__version__"]

# obtain version information
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("passkey")
except PackageNotFoundError:
    __version__ = "unknown"
