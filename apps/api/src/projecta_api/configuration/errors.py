"""Safe errors for the interactive runtime-configuration boundary."""


class ConfigurationProblem(Exception):
    """An expected configuration failure with a finite public error code."""

    def __init__(self, code: str, detail: str, *, status_code: int = 400) -> None:
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class SecretStoreUnavailable(ConfigurationProblem):
    """The approved secret store cannot safely create or resolve a secret."""

    def __init__(self) -> None:
        super().__init__(
            "CONFIGURATION_UNAVAILABLE",
            "The server-side secret store is unavailable.",
            status_code=503,
        )


class ConfigurationConflict(ConfigurationProblem):
    """An optimistic profile revision no longer matches the active profile."""

    def __init__(self) -> None:
        super().__init__(
            "CONFIGURATION_CONFLICT",
            "The LLM profile changed; reload it and retry.",
            status_code=409,
        )


class ConfigurationDisabled(ConfigurationProblem):
    """The requested interactive operation is disabled for this runtime mode."""

    def __init__(self) -> None:
        super().__init__(
            "CONFIGURATION_DISABLED",
            "Interactive runtime configuration is disabled for this deployment.",
            status_code=403,
        )
