"""Discover, classify, and sync clubs for every college configured in the database."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient, ContainerClient
from flask import Flask

from app import create_app
from app.models import College
from jobs.ai.club_filter import IncompleteClassification, run_filter
from jobs.club_discovery.pipeline import run as run_discovery
from sync_clubs import sync_clubs

CACHE_CONTAINER_NAME = "oncamp-discovery-cache"
PROMPT_PATH = Path(__file__).resolve().parents[1] / "ai" / "prompts" / "club_filter.md"


def _get_cache_container() -> ContainerClient:
    connection_string = os.getenv("AzureWebJobsStorage")
    if not connection_string:
        raise RuntimeError("AzureWebJobsStorage must be configured for discovery cache storage.")

    service = BlobServiceClient.from_connection_string(connection_string)
    container = service.get_container_client(CACHE_CONTAINER_NAME)
    try:
        container.create_container()
    except ResourceExistsError:
        pass
    return container


def _cache_blob_name(college_key: str) -> str:
    return f"classifications/{college_key}.json"


def _download_cache(container: ContainerClient, college_key: str, cache_path: Path) -> None:
    blob = container.get_blob_client(_cache_blob_name(college_key))
    if blob.exists():
        cache_path.write_bytes(blob.download_blob().readall())


def _upload_cache(container: ContainerClient, college_key: str, cache_path: Path) -> None:
    if cache_path.exists():
        container.upload_blob(
            name=_cache_blob_name(college_key),
            data=cache_path.read_bytes(),
            overwrite=True,
        )


def _refresh_college(college: College, container: ContainerClient) -> dict[str, Any]:
    if not college.seed_account.strip():
        raise ValueError(f"College {college.key!r} has no seed account configured.")

    with tempfile.TemporaryDirectory(prefix=f"oncamp-{college.key}-") as temp_dir:
        output_dir = Path(temp_dir)
        cache_path = output_dir / "club_classifications.json"
        _download_cache(container, college.key, cache_path)

        discovery = run_discovery(
            college_key=college.key,
            college_name=college.name,
            seed_account=college.seed_account,
            output_dir=str(output_dir),
        )

        clubs_path = output_dir / "clubs.json"
        try:
            classification = run_filter(
                input_path=output_dir / "following.json",
                filtered_output_path=clubs_path,
                prompt_path=PROMPT_PATH,
                cache_path=cache_path,
            )
        except (IncompleteClassification, ValueError):
            _upload_cache(container, college.key, cache_path)
            raise

        _upload_cache(container, college.key, cache_path)
        clubs = json.loads(clubs_path.read_text(encoding="utf-8"))
        sync_summary = sync_clubs(clubs, college_key=college.key)

    return {
        "college_key": college.key,
        "college_name": college.name,
        "seed_account": discovery["seed_account"],
        "following_count": classification["original_count"],
        "club_count": classification["filtered_count"],
        "skipped_count": classification["skipped_count"],
        "sync": sync_summary,
    }


def run_semester_discovery(app: Flask | None = None) -> dict[str, Any]:
    """Refresh all database-configured colleges and sync approved clubs to Postgres."""
    if app is None:
        database_url = os.getenv("DATABASE_URL", "")
        if not database_url or database_url.lower().startswith("sqlite"):
            raise RuntimeError("Set DATABASE_URL to a persistent PostgreSQL database before scheduling discovery.")
        app = create_app()

    with app.app_context():
        colleges = College.query.order_by(College.key).all()
        if not colleges:
            raise RuntimeError("No supported colleges are configured in the colleges table.")

        container = _get_cache_container()
        results = [_refresh_college(college, container) for college in colleges]

    return {"college_count": len(results), "colleges": results}
