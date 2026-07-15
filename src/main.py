"""30 Hz fusion loop: UDP ingest + fuse + send to display."""

import argparse
import socket
import threading
import time

from src.buffers import PoseStore
from src.config import (
    BUFFER_SIZE,
    CAMERA_IDS,
    DISPLAY_HOST,
    DISPLAY_PORT,
    FUSION_HZ,
    INGEST_PORT,
    SYNC_OFFSET_MS,
)
from src.fusion import fuse_poses
from src.receiver import run_receiver
from src.sender import send_fused_pose


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Outpost pose fusion node")
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Skip sending fused poses (ingest + fuse only)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-camera ingest and fusion stats",
    )
    parser.add_argument(
        "--viz",
        action="store_true",
        help="Show live 3D matplotlib view of fused pose in world XYZ space",
    )
    parser.add_argument(
        "--viz-cameras",
        action="store_true",
        help="Show side-by-side 2D camera views with pose overlay for each phone",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    store = PoseStore(CAMERA_IDS, BUFFER_SIZE)
    stop = threading.Event()

    rx = threading.Thread(target=run_receiver, args=(store, stop), daemon=True)
    rx.start()

    display_sock = None if args.no_display else socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    interval = 1.0 / FUSION_HZ
    frame_id = 0
    last_seq: dict[str, int] = {}
    stats_start = time.perf_counter()
    fused_count = 0

    dest = "disabled" if args.no_display else f"{DISPLAY_HOST}:{DISPLAY_PORT}"
    print(f"Listening UDP :{INGEST_PORT} | Fusion {FUSION_HZ} Hz → {dest}")

    visualizer = None
    camera_visualizer = None
    if args.viz or args.viz_cameras:
        try:
            from src.visualize import DualCameraPoseVisualizer, PoseVisualizer3D
        except ImportError as exc:
            raise SystemExit(
                "matplotlib is required for --viz / --viz-cameras. "
                'Install with: pip install -e ".[viz]"'
            ) from exc
        if args.viz:
            visualizer = PoseVisualizer3D()
            print("3D visualization enabled (close window or Ctrl+C to stop)")
        if args.viz_cameras:
            camera_visualizer = DualCameraPoseVisualizer(CAMERA_IDS)
            print("Camera overlay view enabled (close window or Ctrl+C to stop)")

    try:
        while True:
            t0 = time.perf_counter()
            now_ms = int(time.time() * 1000)
            target_ms = now_ms - SYNC_OFFSET_MS

            if args.verbose:
                for cid, latest in store.latest_all().items():
                    if latest and last_seq.get(cid) != latest.seq:
                        last_seq[cid] = latest.seq
                        age = now_ms - latest.t_capture_ms
                        print(
                            f"ingest {cid} seq={latest.seq} "
                            f"from {latest.source_ip} age={age}ms"
                        )
            frames = store.nearest_all(target_ms)
            fused = fuse_poses(frames, target_ms, frame_id)
            if camera_visualizer is not None and not camera_visualizer.update(frames, fused):
                print("Camera visualization window closed")
                break
            if fused:
                if display_sock is not None:
                    send_fused_pose(display_sock, fused)
                if visualizer is not None and not visualizer.update(fused):
                    print("Visualization window closed")
                    break
                frame_id += 1
                fused_count += 1
                if args.verbose:
                    print(
                        f"fused frame_id={fused.frame_id} "
                        f"cameras={fused.cameras_used}"
                    )
                elif fused_count == 1 or fused_count % 30 == 0:
                    elapsed = time.perf_counter() - stats_start
                    fps = fused_count / elapsed if elapsed > 0 else 0.0
                    print(
                        f"fused frame_id={fused.frame_id} "
                        f"cameras={fused.cameras_used} fps≈{fps:.1f}"
                    )
                    if elapsed >= 2.0:
                        fused_count = 0
                        stats_start = time.perf_counter()
            else:
                print("fused brokey")

            elapsed = time.perf_counter() - t0
            time.sleep(max(0.0, interval - elapsed))
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        rx.join(timeout=1.0)
        if display_sock is not None:
            display_sock.close()
        if visualizer is not None:
            visualizer.close()
        if camera_visualizer is not None:
            camera_visualizer.close()


if __name__ == "__main__":
    main()
