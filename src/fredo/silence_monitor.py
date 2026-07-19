from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

_REPROMPT = {
    "en": "Sorry, are you still there?",
    "fr": "Excusez-moi, êtes-vous toujours là ?",
}
_GOODBYE = {
    "en": "I can't hear anyone, so I'll try again another time. Goodbye.",
    "fr": "Je n'entends personne, je réessaierai plus tard. Au revoir.",
}


class SilenceMonitor:
    """Handle a quiet line gracefully instead of letting the model guess.

    The monitor arms a timer whenever the agent finishes speaking and resets it
    whenever the caller starts speaking. On the first timeout it asks the caller
    to confirm they are there; on the second it says goodbye and ends the call.
    This keeps a noisy or silent line from being read as a spoken answer.
    """

    def __init__(
        self,
        *,
        inject_message: Callable[[str], Awaitable[None]],
        on_timeout: Callable[[], Awaitable[None]],
        language: str,
        reprompt_seconds: int,
        goodbye_seconds: int,
    ) -> None:
        self._inject_message = inject_message
        self._on_timeout = on_timeout
        self._language = "fr" if language == "fr" else "en"
        self._reprompt_seconds = reprompt_seconds
        self._goodbye_seconds = goodbye_seconds
        self._attempt = 0
        self._timer: asyncio.Task[None] | None = None
        self._stopped = False

    def notify_agent_audio_done(self) -> None:
        if not self._stopped:
            self._arm()

    def notify_user_started_speaking(self) -> None:
        if self._stopped:
            return
        # A real human turn clears any pending prompt and resets the escalation.
        self._attempt = 0
        self._arm()

    def stop(self) -> None:
        self._stopped = True
        self._cancel()

    def _arm(self) -> None:
        self._cancel()
        if self._attempt == 0:
            wait = self._reprompt_seconds
        elif self._attempt == 1:
            wait = self._goodbye_seconds
        else:
            return
        self._timer = asyncio.create_task(self._run(wait))

    def _cancel(self) -> None:
        if self._timer and not self._timer.done():
            self._timer.cancel()
        self._timer = None

    async def _run(self, seconds: float) -> None:
        try:
            await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            return
        if self._stopped:
            return
        if self._attempt == 0:
            self._attempt = 1
            try:
                await self._inject_message(_REPROMPT[self._language])
            except Exception:
                logger.debug("Silence reprompt injection failed", exc_info=True)
            # Next timer arms on the following AgentAudioDone.
        elif self._attempt == 1:
            self._attempt = 2
            try:
                await self._inject_message(_GOODBYE[self._language])
            except Exception:
                logger.debug("Silence goodbye injection failed", exc_info=True)
            try:
                await self._on_timeout()
            except Exception:
                logger.warning("Silence timeout hangup failed", exc_info=True)
