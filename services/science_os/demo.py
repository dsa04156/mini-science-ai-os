from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import time


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("cpu", "gpu"), default="cpu")
    args = parser.parse_args()
    job_id = os.getenv("SCIENCE_JOB_ID", "local-demo")
    started = time.time()
    result = {
        "science_job_id": job_id,
        "tenant": os.getenv("SCIENCE_TENANT", "unknown"),
        "project": os.getenv("SCIENCE_PROJECT", "unknown"),
        "experiment": os.getenv("SCIENCE_EXPERIMENT", "unknown"),
        "git_commit": os.getenv("SCIENCE_GIT_COMMIT", "unknown"),
        "container_image": os.getenv("SCIENCE_CONTAINER_IMAGE", "unknown"),
        "dataset_version": os.getenv("SCIENCE_DATASET_VERSION", "unknown"),
        "mode": args.mode,
        "node": socket.gethostname(),
        "accelerator": args.mode,
        "platform": platform.platform(),
        "status": "success",
        "params": {"mode": args.mode, "epochs": 1, "seed": 7},
        "metrics": {
            "loss": 0.125 if args.mode == "cpu" else 0.095,
            "accuracy": 0.875 if args.mode == "cpu" else 0.905,
            "duration_seconds": time.time() - started,
        },
    }
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
