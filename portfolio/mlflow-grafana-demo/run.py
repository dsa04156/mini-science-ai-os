import json
import os
import time
from pathlib import Path

import mlflow
from mlflow import MlflowClient


TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
EXPERIMENT_NAME = "nais-functional-demo"
MODEL_NAME = "nais-demo-mean-baseline"


class MeanBaseline(mlflow.pyfunc.PythonModel):
    def predict(self, model_input: list[float]) -> list[float]:
        return [0.5] * len(model_input)


def wait_until_ready(client: MlflowClient, attempts: int = 30) -> None:
    for attempt in range(1, attempts + 1):
        try:
            client.search_experiments(max_results=1)
            return
        except Exception:
            if attempt == attempts:
                raise
            time.sleep(2)


def main() -> None:
    mlflow.set_tracking_uri(TRACKING_URI)
    client = MlflowClient(tracking_uri=TRACKING_URI)
    wait_until_ready(client)
    mlflow.set_experiment(EXPERIMENT_NAME)

    with mlflow.start_run(run_name="functional-smoke") as run:
        mlflow.log_params(
            {
                "algorithm": "mean-baseline",
                "dataset": "synthetic-observations-v1",
                "purpose": "NAIS interview functional proof",
            }
        )
        mlflow.log_metrics({"mae": 0.125, "samples": 8})
        mlflow.set_tags(
            {
                "validation": "live-cluster",
                "availability_scope": "single-instance-poc",
            }
        )

        summary_path = Path("/tmp/summary.json")
        summary_path.write_text(
            json.dumps(
                {
                    "result": "passed",
                    "records": 8,
                    "metric": {"mae": 0.125},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        mlflow.log_artifact(str(summary_path), artifact_path="evidence")
        model = mlflow.pyfunc.log_model(
            name="model",
            python_model=MeanBaseline(),
            input_example=[0.1, 0.9],
        )
        version = mlflow.register_model(model.model_uri, MODEL_NAME)
        client.set_registered_model_alias(MODEL_NAME, "champion", version.version)

        print(
            json.dumps(
                {
                    "experiment": EXPERIMENT_NAME,
                    "run_id": run.info.run_id,
                    "registered_model": MODEL_NAME,
                    "model_version": version.version,
                    "alias": "champion",
                    "status": "passed",
                }
            )
        )


if __name__ == "__main__":
    main()
