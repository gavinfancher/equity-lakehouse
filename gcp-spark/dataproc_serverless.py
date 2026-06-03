#!/usr/bin/env python3
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PySparkBatchSpec:
    project_id: str
    region: str
    batch_id: str
    main_python_file: str
    artifact_bucket: str
    artifact_prefix: str | None = None
    staging_bucket: str | None = None
    run_manifest: dict[str, Any] | None = None
    run_manifest_uri: str | None = None
    manifest_arg_name: str = "--config"
    args: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    runtime_version: str | None = None
    container_image: str | None = None
    ttl: str | int | None = None
    service_account: str | None = None
    network_uri: str | None = None
    subnetwork_uri: str | None = None
    network_tags: list[str] = field(default_factory=list)
    kms_key: str | None = None
    request_id: str | None = None
    python_file_uris: list[str] = field(default_factory=list)
    jar_file_uris: list[str] = field(default_factory=list)
    file_uris: list[str] = field(default_factory=list)
    archive_uris: list[str] = field(default_factory=list)


def parse_gs_uri(uri: str) -> tuple[str, str]:
    match = re.fullmatch(r"gs://([^/]+)/(.+)", uri)
    if not match:
        raise ValueError(f"Expected a gs://bucket/object URI, got {uri}")
    return match.group(1), match.group(2)


def bucket_name(value: str) -> str:
    if value.startswith("gs://"):
        return value.removeprefix("gs://").strip("/")
    return value


def artifact_prefix(spec: PySparkBatchSpec) -> str:
    return (spec.artifact_prefix or f"dataproc/batches/{spec.batch_id}").strip("/")


def main_python_file_uri(spec: PySparkBatchSpec) -> str:
    if spec.main_python_file.startswith("gs://"):
        return spec.main_python_file
    filename = Path(spec.main_python_file).name
    return f"gs://{bucket_name(spec.artifact_bucket)}/{artifact_prefix(spec)}/{filename}"


def run_manifest_uri(spec: PySparkBatchSpec) -> str | None:
    if spec.run_manifest is None:
        return None
    if spec.run_manifest_uri:
        return spec.run_manifest_uri
    return f"gs://{bucket_name(spec.artifact_bucket)}/{artifact_prefix(spec)}/run_manifest.json"


def batch_args(spec: PySparkBatchSpec) -> list[str]:
    args = list(spec.args)
    manifest_uri = run_manifest_uri(spec)
    if manifest_uri:
        args.extend([spec.manifest_arg_name, manifest_uri])
    return args


def stringify_properties(properties: dict[str, Any]) -> dict[str, str]:
    return {key: str(value) for key, value in properties.items()}


def parse_duration_seconds(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value

    match = re.fullmatch(r"(\d+)([smhd]?)", str(value).strip())
    if not match:
        raise ValueError(f"Invalid duration {value!r}; use seconds, 30m, 2h, or 1d")
    amount = int(match.group(1))
    unit = match.group(2) or "s"
    return amount * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


def submission_plan(spec: PySparkBatchSpec) -> dict[str, Any]:
    return {
        "parent": f"projects/{spec.project_id}/locations/{spec.region}",
        "batch_id": spec.batch_id,
        "request_id": spec.request_id,
        "main_python_file_uri": main_python_file_uri(spec),
        "args": batch_args(spec),
        "run_manifest_uri": run_manifest_uri(spec),
        "run_manifest": spec.run_manifest,
        "runtime_config": {
            "version": spec.runtime_version,
            "container_image": spec.container_image,
            "properties": stringify_properties(spec.properties),
        },
        "environment_config": {
            "staging_bucket": bucket_name(spec.staging_bucket)
            if spec.staging_bucket
            else None,
            "ttl_seconds": parse_duration_seconds(spec.ttl),
            "service_account": spec.service_account,
            "network_uri": spec.network_uri,
            "subnetwork_uri": spec.subnetwork_uri,
            "network_tags": spec.network_tags,
            "kms_key": spec.kms_key,
        },
        "labels": spec.labels,
        "source_spec": asdict(spec),
    }


def upload_file(storage_client: Any, local_path: str, destination_uri: str) -> str:
    bucket, name = parse_gs_uri(destination_uri)
    storage_client.bucket(bucket).blob(name).upload_from_filename(local_path)
    return destination_uri


def upload_json(storage_client: Any, value: dict[str, Any], destination_uri: str) -> str:
    bucket, name = parse_gs_uri(destination_uri)
    storage_client.bucket(bucket).blob(name).upload_from_string(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        content_type="application/json",
    )
    return destination_uri


def submit_pyspark_batch(spec: PySparkBatchSpec, wait: bool = True) -> Any:
    from google.cloud import dataproc_v1
    from google.cloud import storage
    from google.protobuf import duration_pb2

    storage_client = storage.Client(project=spec.project_id)
    main_uri = main_python_file_uri(spec)
    if not spec.main_python_file.startswith("gs://"):
        upload_file(storage_client, spec.main_python_file, main_uri)

    manifest_uri = run_manifest_uri(spec)
    if spec.run_manifest is not None and manifest_uri:
        upload_json(storage_client, spec.run_manifest, manifest_uri)

    runtime_config = dataproc_v1.RuntimeConfig(
        properties=stringify_properties(spec.properties)
    )
    if spec.runtime_version:
        runtime_config.version = spec.runtime_version
    if spec.container_image:
        runtime_config.container_image = spec.container_image

    execution_kwargs: dict[str, Any] = {}
    if spec.staging_bucket:
        execution_kwargs["staging_bucket"] = bucket_name(spec.staging_bucket)
    if spec.service_account:
        execution_kwargs["service_account"] = spec.service_account
    if spec.network_uri:
        execution_kwargs["network_uri"] = spec.network_uri
    if spec.subnetwork_uri:
        execution_kwargs["subnetwork_uri"] = spec.subnetwork_uri
    if spec.network_tags:
        execution_kwargs["network_tags"] = spec.network_tags
    if spec.kms_key:
        execution_kwargs["kms_key"] = spec.kms_key

    ttl_seconds = parse_duration_seconds(spec.ttl)
    if ttl_seconds:
        execution_kwargs["ttl"] = duration_pb2.Duration(seconds=ttl_seconds)

    batch_kwargs: dict[str, Any] = {
        "pyspark_batch": dataproc_v1.PySparkBatch(
            main_python_file_uri=main_uri,
            args=batch_args(spec),
            python_file_uris=spec.python_file_uris,
            jar_file_uris=spec.jar_file_uris,
            file_uris=spec.file_uris,
            archive_uris=spec.archive_uris,
        ),
        "runtime_config": runtime_config,
        "labels": spec.labels,
    }
    if execution_kwargs:
        batch_kwargs["environment_config"] = dataproc_v1.EnvironmentConfig(
            execution_config=dataproc_v1.ExecutionConfig(**execution_kwargs)
        )

    client = dataproc_v1.BatchControllerClient(
        client_options={"api_endpoint": f"{spec.region}-dataproc.googleapis.com:443"}
    )
    parent = f"projects/{spec.project_id}/locations/{spec.region}"
    request = dataproc_v1.CreateBatchRequest(
        parent=parent,
        batch=dataproc_v1.Batch(**batch_kwargs),
        batch_id=spec.batch_id,
        request_id=spec.request_id or str(uuid.uuid4()),
    )

    operation = client.create_batch(request=request)
    print(f"Submitted batch: {parent}/batches/{spec.batch_id}")
    print(f"Operation: {operation.operation.name}")
    print(f"Main script: {main_uri}")
    if manifest_uri:
        print(f"Run manifest: {manifest_uri}")

    if not wait:
        return operation

    response = operation.result()
    print(f"Finished batch: {response.name}")
    print(f"State: {dataproc_v1.Batch.State(response.state).name}")
    if response.state_message:
        print(f"State message: {response.state_message}")
    return response
