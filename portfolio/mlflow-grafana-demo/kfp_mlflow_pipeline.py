#!/usr/bin/env python3
"""Compile or submit the Kubeflow Pipelines to MLflow integration demo."""

import argparse
import json
from pathlib import Path

from kfp import Client, compiler, dsl


PIPELINE_NAME = "nais-kfp-mlflow-integration"
DEFAULT_PACKAGE = Path(__file__).with_name("nais-kfp-mlflow-integration.yaml")
DEFAULT_PIPELINE_ROOT = "s3://kubeflow-pipelines/v2/artifacts"


COMPONENT_SCRIPT = r"""
import argparse
import json
import os
import time
from pathlib import Path

os.environ.setdefault("HOME", "/tmp")
os.environ.setdefault("USER", "mlflow")
os.environ.setdefault("LOGNAME", "mlflow")
os.environ.setdefault("GIT_PYTHON_REFRESH", "quiet")

import mlflow
from mlflow import MlflowClient


class MeanBaseline(mlflow.pyfunc.PythonModel):
    def predict(self, model_input):
        return [0.5] * len(model_input)


def wait_until_ready(client, attempts=30):
    for attempt in range(1, attempts + 1):
        try:
            client.search_experiments(max_results=1)
            return
        except Exception:
            if attempt == attempts:
                raise
            time.sleep(2)


parser = argparse.ArgumentParser()
parser.add_argument("--tracking-uri", required=True)
parser.add_argument("--experiment-name", required=True)
parser.add_argument("--model-name", required=True)
parser.add_argument("--dataset-version", required=True)
parser.add_argument("--mae", required=True, type=float)
parser.add_argument("--registration-threshold", required=True, type=float)
args = parser.parse_args()

mlflow.set_tracking_uri(args.tracking_uri)
client = MlflowClient(tracking_uri=args.tracking_uri)
wait_until_ready(client)
mlflow.set_experiment(args.experiment_name)

with mlflow.start_run(run_name="kubeflow-train-register") as run:
    mlflow.log_params(
        {
            "algorithm": "mean-baseline",
            "dataset_version": args.dataset_version,
            "orchestrator": "kubeflow-pipelines",
            "registration_threshold": args.registration_threshold,
        }
    )
    mlflow.log_metrics({"mae": args.mae, "samples": 8})
    mlflow.set_tags(
        {
            "integration": "kubeflow-to-mlflow",
            "validation": "live-cluster",
            "availability_scope": "single-instance-poc",
        }
    )

    passed = args.mae <= args.registration_threshold
    summary = {
        "pipeline": "nais-kfp-mlflow-integration",
        "result": "passed" if passed else "rejected",
        "records": 8,
        "metric": {"mae": args.mae},
        "registration_threshold": args.registration_threshold,
    }
    summary_path = Path("/tmp/kfp-mlflow-summary.json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    mlflow.log_artifact(str(summary_path), artifact_path="evidence")

    result = {
        "experiment": args.experiment_name,
        "run_id": run.info.run_id,
        "registered_model": None,
        "model_version": None,
        "alias": None,
        "status": summary["result"],
    }
    if passed:
        model = mlflow.pyfunc.log_model(
            name="model",
            python_model=MeanBaseline(),
            input_example=[0.1, 0.9],
        )
        version = mlflow.register_model(model.model_uri, args.model_name)
        client.set_registered_model_alias(args.model_name, "candidate", version.version)
        result.update(
            {
                "registered_model": args.model_name,
                "model_version": version.version,
                "alias": "candidate",
            }
        )

    print(json.dumps(result, sort_keys=True))
    if not passed:
        raise SystemExit(
            f"MAE {args.mae} exceeded registration threshold "
            f"{args.registration_threshold}"
        )
"""


@dsl.container_component
def train_register_component(
    tracking_uri: str,
    experiment_name: str,
    model_name: str,
    dataset_version: str,
    mae: float,
    registration_threshold: float,
) -> dsl.ContainerSpec:
    return dsl.ContainerSpec(
        image="ghcr.io/mlflow/mlflow:v3.13.0",
        command=["python", "-c"],
        args=[
            COMPONENT_SCRIPT,
            "--tracking-uri",
            tracking_uri,
            "--experiment-name",
            experiment_name,
            "--model-name",
            model_name,
            "--dataset-version",
            dataset_version,
            "--mae",
            mae,
            "--registration-threshold",
            registration_threshold,
        ],
    )


@dsl.pipeline(
    name=PIPELINE_NAME,
    description="CPU-only Kubeflow Pipeline that records and registers a model in MLflow.",
)
def kfp_mlflow_pipeline(
    tracking_uri: str = "http://mlflow.science-ai-mlops.svc.cluster.local:5000",
    experiment_name: str = "nais-kfp-mlflow-integration",
    model_name: str = "nais-kfp-mean-baseline",
    dataset_version: str = "synthetic-observations-v2",
    mae: float = 0.09,
    registration_threshold: float = 0.1,
) -> None:
    task = train_register_component(
        tracking_uri=tracking_uri,
        experiment_name=experiment_name,
        model_name=model_name,
        dataset_version=dataset_version,
        mae=mae,
        registration_threshold=registration_threshold,
    )
    task.set_display_name("Train, evaluate, and register candidate")
    task.set_caching_options(False)
    task.set_cpu_request("100m")
    task.set_cpu_limit("500m")
    task.set_memory_request("256Mi")
    task.set_memory_limit("1Gi")


def compile_pipeline(package_path: Path) -> None:
    package_path.parent.mkdir(parents=True, exist_ok=True)
    compiler.Compiler().compile(
        pipeline_func=kfp_mlflow_pipeline,
        package_path=str(package_path),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("compile", "submit"))
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--host", default="http://127.0.0.1:18888")
    parser.add_argument("--experiment", default="NAIS integration demos")
    parser.add_argument("--run-name", default=PIPELINE_NAME)
    parser.add_argument("--service-account", default="pipeline-runner")
    args = parser.parse_args()

    compile_pipeline(args.package)
    if args.action == "compile":
        print(args.package)
        return

    client = Client(host=args.host)
    run = client.create_run_from_pipeline_package(
        pipeline_file=str(args.package),
        run_name=args.run_name,
        experiment_name=args.experiment,
        namespace="kubeflow",
        pipeline_root=DEFAULT_PIPELINE_ROOT,
        enable_caching=False,
        service_account=args.service_account,
    )
    print(json.dumps({"run_id": run.run_id, "run_name": args.run_name}))


if __name__ == "__main__":
    main()
