#!/usr/bin/env python3
"""Run MediaPipe Pose on a camera/video stream and send landmarks over UDP."""

from __future__ import annotations

import argparse
import socket
import threading
import time

from pose_factory import make_packet


def _video_source(value: str) -> int | str:
    try:
        return int(value)
    except ValueError:
        return value


class FreshestFrame(threading.Thread):
    """Continuously read a capture, keeping only the most recent frame.

    MediaPipe inference is often slower than the capture rate, which lets
    OpenCV's internal buffer back up so ``read()`` returns increasingly stale
    frames. Draining the source on a dedicated thread ensures inference always
    runs on the latest frame and ``t_capture_ms`` reflects real capture time.
    """

    def __init__(self, capture: "cv2.VideoCapture") -> None:
        super().__init__(daemon=True)
        self._capture = capture
        self._lock = threading.Lock()
        self._latest: tuple[int, "cv2.Mat"] | None = None
        self._last_seen = -1
        self._new_frame = threading.Condition(self._lock)
        self._running = True

    def run(self) -> None:
        counter = 0
        while self._running:
            ok, image = self._capture.read()
            if not ok:
                break
            t_capture_ms = time.time_ns() // 1_000_000
            counter += 1
            with self._new_frame:
                self._latest = (t_capture_ms, image)
                self._last_seen = counter
                self._new_frame.notify_all()
        with self._new_frame:
            self._running = False
            self._new_frame.notify_all()

    def read(self, seen: int) -> tuple[int, int, "cv2.Mat"] | None:
        """Block until a frame newer than ``seen`` is available.

        Returns ``(sequence, t_capture_ms, image)`` or ``None`` when the source
        has ended.
        """

        with self._new_frame:
            self._new_frame.wait_for(
                lambda: not self._running or self._last_seen > seen
            )
            if self._latest is None or self._last_seen <= seen:
                return None
            t_capture_ms, image = self._latest
            return self._last_seen, t_capture_ms, image

    def stop(self) -> None:
        self._running = False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="192.168.50.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--source", default="0", help="camera index, URL, or video path")
    parser.add_argument("--model-complexity", type=int, choices=(0, 1, 2), default=0)
    args = parser.parse_args()

    try:
        import cv2
        import mediapipe as mp
    except ImportError as exc:
        raise SystemExit('install phone dependencies with: pip install -e ".[phone]"') from exc

    capture = cv2.VideoCapture(_video_source(args.source))
    if not capture.isOpened():
        raise SystemExit(f"could not open video source {args.source!r}")

    destination = (args.host, args.port)
    seq = 0
    reader = FreshestFrame(capture)
    reader.start()
    pose_api = mp.solutions.pose
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock, pose_api.Pose(
        static_image_mode=False,
        model_complexity=args.model_complexity,
        enable_segmentation=False,
    ) as pose:
        seen = -1
        try:
            while True:
                frame = reader.read(seen)
                if frame is None:
                    break
                seen, t_capture_ms, image = frame
                result = pose.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
                if result.pose_landmarks is None:
                    continue
                landmarks = [
                    {
                        "i": index,
                        "x": landmark.x,
                        "y": landmark.y,
                        "z": landmark.z,
                        "v": landmark.visibility,
                    }
                    for index, landmark in enumerate(result.pose_landmarks.landmark)
                ]
                sock.sendto(
                    make_packet(seq, landmarks, t_capture_ms=t_capture_ms),
                    destination,
                )
                seq += 1
        except KeyboardInterrupt:
            pass
        finally:
            reader.stop()
            capture.release()
    print(f"sent {seq} pose frames")


if __name__ == "__main__":
    main()
