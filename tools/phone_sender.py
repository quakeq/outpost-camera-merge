#!/usr/bin/env python3
"""Send MediaPipe pose landmarks over UDP (run on phone or laptop)."""

from __future__ import annotations

import argparse
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pose_factory import make_packet  # noqa: E402


def _open_capture(source: str):
    import cv2

    if source.isdigit():
        return cv2.VideoCapture(int(source))
    return cv2.VideoCapture(source)


def _landmarks_from_results(results) -> list[dict] | None:
    world = results.pose_world_landmarks
    if not world:
        return None
    out: list[dict] = []
    for i, lm in enumerate(world.landmark):
        out.append(
            {
                "i": i,
                "x": lm.x,
                "y": lm.y,
                "z": lm.z,
                "v": lm.visibility,
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MediaPipe pose → UDP packets for outpost fusion ingest"
    )
    parser.add_argument(
        "--host",
        default="192.168.50.1",
        help="Laptop fusion node IP (POSE-LAN default: 192.168.50.1)",
    )
    parser.add_argument("--port", type=int, default=9000, help="Fusion ingest UDP port")
    parser.add_argument(
        "--camera-id",
        default="camera-a",
        choices=("camera-a", "camera-b"),
        help="Must match an ID in outpost.config.CAMERA_IDS",
    )
    parser.add_argument(
        "--source",
        default="0",
        help="Camera index (0) or URL (IP Webcam: http://PHONE_IP:8080/video)",
    )
    parser.add_argument("--hz", type=float, default=30.0, help="Target send rate")
    parser.add_argument(
        "--model-complexity",
        type=int,
        default=1,
        choices=(0, 1, 2),
        help="MediaPipe pose model complexity (0=fast, 2=accurate)",
    )
    args = parser.parse_args()

    import cv2
    import mediapipe as mp

    cap = _open_capture(args.source)
    if not cap.isOpened():
        print(f"Failed to open camera source: {args.source!r}", file=sys.stderr)
        sys.exit(1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    interval = 1.0 / args.hz
    seq = 0
    sent = 0
    window_start = time.perf_counter()

    mp_pose = mp.solutions.pose
    print(
        f"Sending {args.camera_id} @ {args.hz} Hz → {args.host}:{args.port} "
        f"(source={args.source!r})"
    )

    try:
        with mp_pose.Pose(
            model_complexity=args.model_complexity,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        ) as pose:
            while True:
                t0 = time.perf_counter()
                ok, frame = cap.read()
                if not ok:
                    print("Camera read failed", file=sys.stderr)
                    time.sleep(0.1)
                    continue

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = pose.process(rgb)
                landmarks = _landmarks_from_results(results)
                if landmarks is None:
                    elapsed = time.perf_counter() - t0
                    time.sleep(max(0.0, interval - elapsed))
                    continue

                seq += 1
                t_ms = int(time.time() * 1000)
                packet = {
                    "camera_id": args.camera_id,
                    "seq": seq,
                    "t_capture_ms": t_ms,
                    "landmarks": landmarks,
                }
                import json

                sock.sendto(json.dumps(packet).encode("utf-8"), (args.host, args.port))
                sent += 1

                now = time.perf_counter()
                if sent == 1 or sent % 30 == 0:
                    elapsed = now - window_start
                    fps = sent / elapsed if elapsed > 0 else 0.0
                    print(f"seq={seq} landmarks=33 fps≈{fps:.1f}")
                    if elapsed >= 2.0:
                        sent = 0
                        window_start = now

                elapsed = time.perf_counter() - t0
                time.sleep(max(0.0, interval - elapsed))
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        cap.release()
        sock.close()


if __name__ == "__main__":
    main()
