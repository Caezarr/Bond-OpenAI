"""Listen-only live audio: in-memory fan-out, mixing, tokens and encoding.

Design (all in-memory, nothing is ever written to disk):

- `AudioHub` holds one `_Broadcaster` per active call. The voice bridge pushes
  both legs (caller + agent, 8 kHz mu-law) into it. A single mixer loop per call
  sums the two legs into linear PCM frames and fans them out to any listeners.
- `AudioTokenManager` mints short-lived, single-use tokens bound to a call, so a
  stream URL cannot be reused, shared or replayed.
- `encode_pcm_stream` turns mixed PCM into a browser-playable MP3 stream. The MP3
  encoder is an optional dependency; without it live listening reports as
  unavailable and calls run normally.

This module is transport-neutral: it never touches Twilio, Deepgram or storage.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from array import array
from collections.abc import AsyncIterator

# 8 kHz mono, 20 ms frames: 160 samples per frame.
SAMPLE_RATE = 8000
FRAME_SAMPLES = 160
FRAME_BYTES = FRAME_SAMPLES * 2
_FRAME_SECONDS = FRAME_SAMPLES / SAMPLE_RATE
# Cap each leg's jitter buffer so a stalled listener can never grow memory.
_MAX_BUFFERED_SAMPLES = SAMPLE_RATE * 2
_SUBSCRIBER_QUEUE_FRAMES = 50  # ~1 s; drop oldest beyond this.

_MULAW_BIAS = 0x84


def _build_mulaw_table() -> list[int]:
    table: list[int] = []
    for value in range(256):
        muval = ~value & 0xFF
        sign = muval & 0x80
        exponent = (muval >> 4) & 0x07
        mantissa = muval & 0x0F
        magnitude = ((mantissa << 3) + _MULAW_BIAS) << exponent
        magnitude -= _MULAW_BIAS
        table.append(-magnitude if sign else magnitude)
    return table


_MULAW_TABLE = _build_mulaw_table()


def mulaw_to_pcm16(data: bytes) -> array:
    return array("h", (_MULAW_TABLE[b] for b in data))


def _mix(a: array, b: array) -> array:
    """Sum two equal-length PCM frames with hard clipping."""
    out = array("h", bytes(len(a) * 2))
    for i in range(len(a)):
        total = a[i] + b[i]
        out[i] = 32767 if total > 32767 else -32768 if total < -32768 else total
    return out


class _Broadcaster:
    def __init__(self) -> None:
        self._legs: dict[str, array] = {"caller": array("h"), "agent": array("h")}
        self._subscribers: set[asyncio.Queue[bytes | None]] = set()
        self._mixer: asyncio.Task[None] | None = None
        self._closed = False

    def push(self, leg: str, mulaw: bytes) -> None:
        if self._closed or leg not in self._legs:
            return
        buffer = self._legs[leg]
        buffer.extend(mulaw_to_pcm16(mulaw))
        if len(buffer) > _MAX_BUFFERED_SAMPLES:
            del buffer[: len(buffer) - _MAX_BUFFERED_SAMPLES]

    def _take_frame(self, leg: str) -> array:
        buffer = self._legs[leg]
        if len(buffer) >= FRAME_SAMPLES:
            frame = buffer[:FRAME_SAMPLES]
            del buffer[:FRAME_SAMPLES]
            return frame
        return array("h", bytes(FRAME_BYTES))

    def subscribe(self) -> asyncio.Queue[bytes | None]:
        queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=_SUBSCRIBER_QUEUE_FRAMES)
        self._subscribers.add(queue)
        if self._mixer is None or self._mixer.done():
            self._mixer = asyncio.create_task(self._run())
        return queue

    def unsubscribe(self, queue: asyncio.Queue[bytes | None]) -> None:
        self._subscribers.discard(queue)

    @property
    def has_listeners(self) -> bool:
        return bool(self._subscribers)

    async def _run(self) -> None:
        next_tick = time.monotonic()
        while not self._closed and self._subscribers:
            frame = _mix(self._take_frame("caller"), self._take_frame("agent"))
            payload = frame.tobytes()
            for queue in tuple(self._subscribers):
                if queue.full():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                queue.put_nowait(payload)
            next_tick += _FRAME_SECONDS
            await asyncio.sleep(max(0.0, next_tick - time.monotonic()))

    def close(self) -> None:
        self._closed = True
        for queue in tuple(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(None)
        self._subscribers.clear()
        if self._mixer and not self._mixer.done():
            self._mixer.cancel()


class AudioHub:
    def __init__(self) -> None:
        self._calls: dict[str, _Broadcaster] = {}

    def publish(self, call_id: str, leg: str, mulaw: bytes) -> None:
        broadcaster = self._calls.get(call_id)
        if broadcaster is None:
            broadcaster = self._calls[call_id] = _Broadcaster()
        broadcaster.push(leg, mulaw)

    async def listen(self, call_id: str) -> AsyncIterator[bytes]:
        broadcaster = self._calls.get(call_id)
        if broadcaster is None:
            return
        queue = broadcaster.subscribe()
        try:
            while True:
                frame = await queue.get()
                if frame is None:
                    return
                yield frame
        finally:
            broadcaster.unsubscribe(queue)

    def is_live(self, call_id: str) -> bool:
        return call_id in self._calls

    def close(self, call_id: str) -> None:
        broadcaster = self._calls.pop(call_id, None)
        if broadcaster is not None:
            broadcaster.close()


class AudioTokenManager:
    """Short-lived, single-use tokens bound to one call_id."""

    def __init__(self, ttl_seconds: int = 30) -> None:
        self._ttl = ttl_seconds
        self._tokens: dict[str, tuple[str, float]] = {}

    def mint(self, call_id: str) -> tuple[str, float]:
        now = time.time()
        self._tokens = {
            token: entry for token, entry in self._tokens.items() if entry[1] > now
        }
        token = secrets.token_urlsafe(32)
        expires_at = now + self._ttl
        self._tokens[token] = (call_id, expires_at)
        return token, expires_at

    def consume(self, token: str) -> str | None:
        entry = self._tokens.pop(token, None)
        if entry is None:
            return None
        call_id, expires_at = entry
        if time.time() > expires_at:
            return None
        return call_id


def audio_encoding_available() -> bool:
    try:
        import lameenc  # noqa: F401
    except Exception:
        return False
    return True


async def encode_pcm_stream(frames: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    """Encode 8 kHz mono PCM16 frames into a streaming MP3 body."""
    import lameenc

    encoder = lameenc.Encoder()
    encoder.set_in_sample_rate(SAMPLE_RATE)
    encoder.set_channels(1)
    encoder.set_bit_rate(64)
    encoder.set_quality(2)
    encoder.silence()
    try:
        async for frame in frames:
            chunk = encoder.encode(frame)
            if chunk:
                yield bytes(chunk)
    finally:
        tail = encoder.flush()
        if tail:
            yield bytes(tail)


_HUB: AudioHub | None = None
_TOKENS: AudioTokenManager | None = None


def get_audio_hub() -> AudioHub:
    global _HUB
    if _HUB is None:
        _HUB = AudioHub()
    return _HUB


def get_audio_tokens() -> AudioTokenManager:
    global _TOKENS
    if _TOKENS is None:
        _TOKENS = AudioTokenManager()
    return _TOKENS
