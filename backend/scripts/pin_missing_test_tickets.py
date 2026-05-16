"""
Re-fetch any tickets referenced by test-case `expected_keys` that are
missing from the vector DB. Safe to re-run after adding or editing
cases — only the actually-missing keys are fetched.
"""

import asyncio
from pathlib import Path

import yaml
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

from open_webui.retrieval.jira_tickets import (  # noqa: E402
    JIRA_COLLECTION,
    sync_jira_tickets,
)
from open_webui.retrieval.vector.dbs.pgvector import PgvectorClient  # noqa: E402

CASES_DIR = Path(__file__).resolve().parents[2] / "tests" / "cases"


def collect_expected_keys() -> set[str]:
    keys: set[str] = set()
    for yaml_path in sorted(CASES_DIR.glob("*.yaml")):
        with yaml_path.open() as f:
            data = yaml.safe_load(f) or []
        for case in data:
            for key in case.get("expected_keys") or []:
                keys.add(key)
    return keys


def collect_existing_keys() -> set[str]:
    client = PgvectorClient()
    existing = client.get(collection_name=JIRA_COLLECTION)
    keys: set[str] = set()
    if existing and existing.metadatas and existing.metadatas[0]:
        for meta in existing.metadatas[0]:
            if meta and meta.get("key"):
                keys.add(meta["key"])
    return keys


async def main():
    expected = collect_expected_keys()
    existing = collect_existing_keys()
    missing = sorted(expected - existing)

    if not missing:
        print(f"All {len(expected)} expected tickets are present in the vector DB.")
        return

    print(f"Missing {len(missing)}/{len(expected)} expected tickets: {missing}")
    jql = f"key in ({','.join(missing)})"
    count = await sync_jira_tickets(jql=jql)
    print(f"Upserted {count} tickets")


if __name__ == "__main__":
    asyncio.run(main())
