#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Sequence

from dataproc_serverless import PySparkBatchSpec, submission_plan, submit_pyspark_batch


DEFAULT_PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "finpipe-494623")
DEFAULT_REGION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
DEFAULT_BUCKET = os.environ.get("FINPIPE_BUCKET", "finpipe-bucket")
DEFAULT_JOB_FILE = os.environ.get("FINPIPE_OHLC_JOB_FILE", "/Users/gavin/finpipe_ohlc_job.py")


def flatten_inputs(values: Sequence[Sequence[str]] | None) -> list[str]:
    if not values:
        return []

    uris: list[str] = []
    for group in values:
        for value in group:
            uris.extend(item.strip() for item in value.split(",") if item.strip())
    return uris


def parse_key_value(values: Sequence[str] | None) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError(f"Expected KEY=VALUE, got {value!r}")
        key, raw_value = value.split("=", 1)
        parsed[key] = raw_value
    return parsed


def generated_batch_id(prefix: str = "finpipe-ohlc") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{stamp}"


def build_ohlc_run_manifest(
    input_uris: Sequence[str],
    output_uri: str,
    output_partitions: int = 1,
) -> dict[str, Any]:
    if not input_uris:
        raise ValueError("input_uris must contain at least one URI")
    if not output_uri:
        raise ValueError("output_uri is required")

    return {
        "input": list(input_uris),
        "output": output_uri,
        "output_partitions": output_partitions,
    }


def build_spark_properties(
    *,
    initial_executors: int,
    min_executors: int,
    max_executors: int,
    executor_allocation_ratio: float,
    executor_cores: int,
    executor_memory: str,
    driver_cores: int,
    driver_memory: str,
    dataproc_tier: str | None,
    extra_properties: dict[str, str],
) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "spark.dataproc.scaling.version": "2",
        "spark.dynamicAllocation.initialExecutors": initial_executors,
        "spark.dynamicAllocation.minExecutors": min_executors,
        "spark.dynamicAllocation.maxExecutors": max_executors,
        "spark.dynamicAllocation.executorAllocationRatio": executor_allocation_ratio,
        "spark.executor.cores": executor_cores,
        "spark.executor.memory": executor_memory,
        "spark.driver.cores": driver_cores,
        "spark.driver.memory": driver_memory,
    }
    if dataproc_tier:
        properties["dataproc.tier"] = dataproc_tier
    properties.update(extra_properties)
    return properties


def build_ohlc_batch_spec(
    *,
    input_uris: Sequence[str],
    output_uri: str,
    batch_id: str | None = None,
    project_id: str = DEFAULT_PROJECT_ID,
    region: str = DEFAULT_REGION,
    artifact_bucket: str = DEFAULT_BUCKET,
    staging_bucket: str = DEFAULT_BUCKET,
    job_file: str = DEFAULT_JOB_FILE,
    output_partitions: int = 1,
    ttl: str = "1h",
    properties: dict[str, Any] | None = None,
    labels: dict[str, str] | None = None,
    service_account: str | None = None,
    runtime_version: str | None = None,
    request_id: str | None = None,
) -> PySparkBatchSpec:
    resolved_batch_id = batch_id or generated_batch_id()
    run_manifest = build_ohlc_run_manifest(
        input_uris=input_uris,
        output_uri=output_uri,
        output_partitions=output_partitions,
    )

    resolved_labels = {
        "pipeline": "finpipe",
        "asset": "ohlc",
        **(labels or {}),
    }

    return PySparkBatchSpec(
        project_id=project_id,
        region=region,
        batch_id=resolved_batch_id,
        main_python_file=job_file,
        artifact_bucket=artifact_bucket,
        artifact_prefix=f"dataproc/finpipe-ohlc/{resolved_batch_id}",
        staging_bucket=staging_bucket,
        run_manifest=run_manifest,
        properties=properties or {},
        labels=resolved_labels,
        ttl=ttl,
        service_account=service_account,
        runtime_version=runtime_version,
        request_id=request_id,
    )


def run_ohlc_asset(
    *,
    input_uris: Sequence[str],
    output_uri: str,
    wait: bool = True,
    dry_run: bool = False,
    **kwargs: Any,
) -> Any:
    spec = build_ohlc_batch_spec(
        input_uris=input_uris,
        output_uri=output_uri,
        **kwargs,
    )

    if dry_run:
        plan = submission_plan(spec)
        print(json.dumps(plan, indent=2, sort_keys=True))
        return plan

    return submit_pyspark_batch(spec, wait=wait)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simulate the Dagster asset that submits the OHLC PySpark batch."
    )
    parser.add_argument(
        "--input",
        dest="input_groups",
        action="append",
        nargs="+",
        required=True,
        help="Input GCS URI. Repeat the flag or pass multiple values.",
    )
    parser.add_argument("--output", required=True, help="Output GCS URI/directory.")
    parser.add_argument("--batch-id", help="Dataproc batch id. Defaults to timestamped.")
    parser.add_argument("--project-id", default=DEFAULT_PROJECT_ID)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--artifact-bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--staging-bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--job-file", default=DEFAULT_JOB_FILE)
    parser.add_argument("--output-partitions", type=int, default=1)
    parser.add_argument("--ttl", default="1h")
    parser.add_argument("--runtime-version")
    parser.add_argument("--service-account")
    parser.add_argument("--request-id")
    parser.add_argument("--initial-executors", type=int, default=2)
    parser.add_argument("--min-executors", type=int, default=2)
    parser.add_argument("--max-executors", type=int, default=20)
    parser.add_argument("--executor-allocation-ratio", type=float, default=0.5)
    parser.add_argument("--executor-cores", type=int, default=4)
    parser.add_argument("--executor-memory", default="12g")
    parser.add_argument("--driver-cores", type=int, default=4)
    parser.add_argument("--driver-memory", default="8g")
    parser.add_argument("--dataproc-tier", choices=["standard", "premium"])
    parser.add_argument(
        "--property",
        action="append",
        help="Extra Spark property as KEY=VALUE. May be repeated.",
    )
    parser.add_argument(
        "--label",
        action="append",
        help="Extra Dataproc label as KEY=VALUE. May be repeated.",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Submit and return without waiting for the batch to finish.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generated submission plan without uploading or submitting.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_uris = flatten_inputs(args.input_groups)
    extra_properties = parse_key_value(args.property)
    extra_labels = parse_key_value(args.label)

    properties = build_spark_properties(
        initial_executors=args.initial_executors,
        min_executors=args.min_executors,
        max_executors=args.max_executors,
        executor_allocation_ratio=args.executor_allocation_ratio,
        executor_cores=args.executor_cores,
        executor_memory=args.executor_memory,
        driver_cores=args.driver_cores,
        driver_memory=args.driver_memory,
        dataproc_tier=args.dataproc_tier,
        extra_properties=extra_properties,
    )

    run_ohlc_asset(
        input_uris=input_uris,
        output_uri=args.output,
        batch_id=args.batch_id,
        project_id=args.project_id,
        region=args.region,
        artifact_bucket=args.artifact_bucket,
        staging_bucket=args.staging_bucket,
        job_file=args.job_file,
        output_partitions=args.output_partitions,
        ttl=args.ttl,
        properties=properties,
        labels=extra_labels,
        service_account=args.service_account,
        runtime_version=args.runtime_version,
        request_id=args.request_id,
        wait=not args.no_wait,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
