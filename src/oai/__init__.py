"""OAI analytics: data layer and export tooling for Osteoarthritis Initiative analyses."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("oai-analytics")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0"
