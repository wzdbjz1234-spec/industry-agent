"""Background queue that continuously processes arriving frames."""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from datetime import UTC, datetime

from quality_case_agent.contracts.vision import VisionJobContract, VisionStatusContract

from .service import VisionProcessingError, VisionProcessingService
from .types import VisionFrame


@dataclass(frozen=True, slots=True)
class _Job:
    job: VisionJobContract
    frame: VisionFrame


class VisionStreamWorker:
    """Bounded in-memory continuous worker; replace its queue with a broker later."""

    def __init__(self, service: VisionProcessingService, *, max_queue_size: int = 256) -> None:
        self._service = service
        self._queue: queue.Queue[_Job] = queue.Queue(maxsize=max_queue_size)
        self._jobs: dict[str, VisionJobContract] = {}
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._completed = 0
        self._failed = 0

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="vision-worker", daemon=True)
            self._thread.start()

    def submit(self, frame: VisionFrame) -> VisionJobContract:
        self._service.registry.resolve(frame.scheme)
        submitted = VisionJobContract(
            job_id=f"vision-job:{frame.frame_id}",
            frame_id=frame.frame_id,
            scheme=frame.scheme,
            status="QUEUED",
            submitted_at=datetime.now(UTC),
        )
        job = _Job(job=submitted, frame=frame)
        try:
            self._queue.put_nowait(job)
        except queue.Full as exc:
            raise VisionQueueFullError("vision worker queue is full") from exc
        with self._lock:
            self._jobs[submitted.job_id] = submitted
        self.start()
        return submitted

    def get(self, job_id: str) -> VisionJobContract | None:
        with self._lock:
            return self._jobs.get(job_id)

    def status(self) -> VisionStatusContract:
        with self._lock:
            running = self._thread is not None and self._thread.is_alive()
            return VisionStatusContract(
                running=running,
                queued=self._queue.qsize(),
                completed=self._completed,
                failed=self._failed,
                registered_schemes=list(self._service.registry.names()),
            )

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                queued = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            processing = queued.job.model_copy(update={"status": "PROCESSING"})
            self._save(processing)
            try:
                result = self._service.process(queued.frame)
                completed = processing.model_copy(
                    update={
                        "status": "COMPLETED",
                        "completed_at": datetime.now(UTC),
                        "result_id": result.record.result_id,
                        "is_ng": result.record.is_ng,
                        "anomaly_score": result.record.anomaly_score,
                    }
                )
                with self._lock:
                    self._completed += 1
            except VisionProcessingError as exc:
                completed = processing.model_copy(
                    update={
                        "status": "FAILED",
                        "completed_at": datetime.now(UTC),
                        "error": str(exc),
                    }
                )
                with self._lock:
                    self._failed += 1
            except Exception as exc:  # noqa: BLE001 - keep the continuous worker alive.
                completed = processing.model_copy(
                    update={
                        "status": "FAILED",
                        "completed_at": datetime.now(UTC),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                with self._lock:
                    self._failed += 1
            self._save(completed)
            self._queue.task_done()

    def _save(self, job: VisionJobContract) -> None:
        with self._lock:
            self._jobs[job.job_id] = job


class VisionQueueFullError(RuntimeError):
    pass
