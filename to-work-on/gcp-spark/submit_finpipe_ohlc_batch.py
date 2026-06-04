#!/usr/bin/env python3
import argparse
import json
import re
import uuid
from pathlib import Path

from google.cloud import dataproc_v1
from google.cloud import storage
from google.protobuf import duration_pb2


DEFAULT_PROPERTIES = {
    "spark.dataproc.scaling.version": "2",
    "spark.dynamicAllocation.initialExecutors": "2",
    "spark.dynamicAllocation.minExecutors": "2",
    "spark.dynamicAllocation.maxExecutors": "20",
    "spark.dynamicAllocation.executorAllocationRatio": "0.5",
    "spark.executor.cores": "4",
    "spark.executor.memory": "12g",
    "spark.driver.cores": "4",
    "spark.driver.memory": "8g",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Submit the finpipe OHLC PySpark job to Dataproc Serverless."
    )
    parser.add_argument("config", help="Local JSON batch config path.")
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Submit the batch and return without waiting for completion.",
    )
    return parser.parse_args()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_gs_uri(uri):
    match = re.fullmatch(r"gs://([^/]+)/(.+)", uri)
    if not match:
        raise ValueError(f"Expected a gs://bucket/object URI, got {uri}")
    return match.group(1), match.group(2)


def bucket_name(value):
    if value.startswith("gs://"):
        return value.removeprefix("gs://").strip("/")
    return value


def upload_file(storage_client, local_path, destination_uri):
    bucket, name = parse_gs_uri(destination_uri)
    blob = storage_client.bucket(bucket).blob(name)
    blob.upload_from_filename(local_path)
    return destination_uri


def upload_json(storage_client, value, destination_uri):
    bucket, name = parse_gs_uri(destination_uri)
    blob = storage_client.bucket(bucket).blob(name)
    blob.upload_from_string(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        content_type="application/json",
    )
    return destination_uri


def parse_duration(value):
    if value is None:
        return None
    if isinstance(value, int):
        seconds = value
    else:
        match = re.fullmatch(r"(\d+)([smhd]?)", str(value).strip())
        if not match:
            raise ValueError(f"Invalid duration {value!r}; use seconds, 30m, 2h, or 1d")
        amount = int(match.group(1))
        unit = match.group(2) or "s"
        multiplier = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
        seconds = amount * multiplier

    duration = duration_pb2.Duration()
    duration.seconds = seconds
    return duration


def build_run_config(config):
    if "run_config" in config:
        return config["run_config"]

    required = ["input", "output"]
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"Missing required config keys: {', '.join(missing)}")

    run_config = {
        "input": config["input"],
        "output": config["output"],
    }
    if "output_partitions" in config:
        run_config["output_partitions"] = config["output_partitions"]
    return run_config


def build_batch(config, main_python_file_uri, run_config_uri):
    properties = {**DEFAULT_PROPERTIES, **config.get("properties", {})}

    runtime_config = dataproc_v1.RuntimeConfig(properties=properties)
    if config.get("runtime_version"):
        runtime_config.version = config["runtime_version"]
    if config.get("container_image"):
        runtime_config.container_image = config["container_image"]

    execution_kwargs = {}
    if config.get("staging_bucket"):
        execution_kwargs["staging_bucket"] = bucket_name(config["staging_bucket"])
    if config.get("service_account"):
        execution_kwargs["service_account"] = config["service_account"]
    if config.get("ttl"):
        execution_kwargs["ttl"] = parse_duration(config["ttl"])

    batch_kwargs = {
        "pyspark_batch": dataproc_v1.PySparkBatch(
            main_python_file_uri=main_python_file_uri,
            args=["--config", run_config_uri],
        ),
        "runtime_config": runtime_config,
        "labels": config.get("labels", {}),
    }
    if execution_kwargs:
        batch_kwargs["environment_config"] = dataproc_v1.EnvironmentConfig(
            execution_config=dataproc_v1.ExecutionConfig(**execution_kwargs)
        )

    return dataproc_v1.Batch(**batch_kwargs)


def submit_batch(config, wait=True):
    project_id = config["project_id"]
    region = config["region"]
    batch_id = config["batch_id"]
    artifact_bucket = bucket_name(config.get("artifact_bucket", config["staging_bucket"]))
    artifact_prefix = config.get("artifact_prefix", f"dataproc/finpipe-ohlc/{batch_id}")

    storage_client = storage.Client(project=project_id)

    main_python_file_uri = config.get("main_python_file_uri")
    if not main_python_file_uri:
        job_file = config.get("job_file", "/Users/gavin/finpipe_ohlc_job.py")
        main_python_file_uri = (
            f"gs://{artifact_bucket}/{artifact_prefix}/finpipe_ohlc_job.py"
        )
        upload_file(storage_client, job_file, main_python_file_uri)

    run_config_uri = config.get(
        "run_config_uri", f"gs://{artifact_bucket}/{artifact_prefix}/run_config.json"
    )
    upload_json(storage_client, build_run_config(config), run_config_uri)

    client = dataproc_v1.BatchControllerClient(
        client_options={"api_endpoint": f"{region}-dataproc.googleapis.com:443"}
    )
    parent = f"projects/{project_id}/locations/{region}"
    request = dataproc_v1.CreateBatchRequest(
        parent=parent,
        batch=build_batch(config, main_python_file_uri, run_config_uri),
        batch_id=batch_id,
        request_id=config.get("request_id", str(uuid.uuid4())),
    )

    operation = client.create_batch(request=request)
    print(f"Submitted batch: {parent}/batches/{batch_id}")
    print(f"Operation: {operation.operation.name}")
    print(f"Main script: {main_python_file_uri}")
    print(f"Run config: {run_config_uri}")

    if not wait:
        return operation

    response = operation.result()
    print(f"Finished batch: {response.name}")
    print(f"State: {dataproc_v1.Batch.State(response.state).name}")
    if response.state_message:
        print(f"State message: {response.state_message}")
    return response


def main():
    args = parse_args()
    config = load_json(args.config)
    submit_batch(config, wait=not args.no_wait)


if __name__ == "__main__":
    main()
