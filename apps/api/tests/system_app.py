"""Deterministic HTTP runtime used only by the canonical Compose system suite."""

import os
from pathlib import Path

from projecta_api.config import Settings
from projecta_api.llm.replay import ReplayGateway
from projecta_api.main import create_app

fixture = Path(os.environ["PROJECTA_REPLAY_FIXTURE"])
app = create_app(settings=Settings(), gateway=ReplayGateway.from_file(fixture))  # pyright: ignore[reportCallIssue]
