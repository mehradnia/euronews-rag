import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

PipelineStep = Callable[[], Awaitable[None]]


class PipelineComposer:
    """Manages an ordered sequence of async pipeline steps."""

    def __init__(self) -> None:
        self._steps: list[tuple[str, PipelineStep]] = []

    def add_step(self, name: str, step: PipelineStep) -> None:
        self._steps.append((name, step))

    async def run(self) -> None:
        logger.info("Pipeline started (%d steps)", len(self._steps))
        for name, step in self._steps:
            logger.info("Running step: %s", name)
            await step()
            logger.info("Completed step: %s", name)
        logger.info("Pipeline finished")
