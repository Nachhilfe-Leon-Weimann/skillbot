class SkillForgeError(Exception):
    """Base class for SkillForge-related errors."""


class SkillForgeUnavailable(SkillForgeError):
    """Raised when the SkillForge service is unavailable."""


class SkillForgeTimeout(SkillForgeError):
    """Raised when a request to the SkillForge service times out."""


class SkillForgeClientAuthenticationError(SkillForgeError):
    """Raised when the SkillForge client fails to authenticate."""


class SkillForgeResponseError(SkillForgeError):
    """Raised when the SkillForge service returns an unexpected response."""
