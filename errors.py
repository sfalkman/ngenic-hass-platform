"""Errors for the Ngenic Tune component."""
from homeassistant.exceptions import HomeAssistantError


class NgenicException(HomeAssistantError):
    """Base class for Ngenic exceptions."""


class AlreadyConfigured(NgenicException):
    """Device is already configured."""

class NoTunes(NgenicException):
    """No tunes."""