"""
Same start()/stop() shape as android-client's AudioRecorder.kt, and
the same target format (16kHz mono 16-bit WAV) so the server's STT
never has to transcode.
"""
import queue
import wave
from pathlib import Path

import sounddevice as sd

SAMPLE_RATE = 16_000
CHANNELS = 1


class AudioRecorder:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._queue: "queue.Queue[bytes]" = queue.Queue()
        self._stream: sd.RawInputStream | None = None

    def start(self) -> None:
        self._queue = queue.Queue()

        def _callback(indata, frames, time_info, status):  # noqa: ARG001
            self._queue.put(bytes(indata))

        self._stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16", callback=_callback,
        )
        self._stream.start()

    def stop(self) -> Path:
        assert self._stream is not None, "start() was never called"
        self._stream.stop()
        self._stream.close()
        self._stream = None

        wav_path = self.output_dir / f"entry_{_now_ms()}.wav"
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(SAMPLE_RATE)
            while not self._queue.empty():
                wf.writeframes(self._queue.get())
        return wav_path


def _now_ms() -> int:
    import time

    return int(time.time() * 1000)
