"""
Dump the current Jira ticket pool to docs/jira_tickets_list.md.

Source is the vector DB rather than a fresh Jira fetch — that way the file
reflects exactly what the agent can retrieve (including any tickets pinned
via pin_missing_test_tickets.py that fall outside the latest-N sync window).
"""

from pathlib import Path

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

from open_webui.retrieval.jira_tickets import JIRA_COLLECTION  # noqa: E402
from open_webui.retrieval.vector.dbs.pgvector import PgvectorClient  # noqa: E402

OUTPUT = Path(__file__).resolve().parents[2] / "docs" / "jira_tickets_list.md"
SEPARATOR = "-" * 43


def parse_ticket_text(text: str) -> tuple[str, str]:
    summary = ""
    desc_lines: list[str] = []
    in_description = False
    for line in (text or "").split("\n"):
        if line.startswith("Summary:"):
            summary = line[len("Summary:") :].strip()
            in_description = False
        elif line.startswith("Description:"):
            desc_lines.append(line[len("Description:") :].lstrip())
            in_description = True
        elif line.startswith(("Key:", "Status:", "Type:", "Priority:", "Assignee:")):
            in_description = False
        elif in_description:
            desc_lines.append(line)
    return summary, "\n".join(desc_lines).rstrip()


def main():
    client = PgvectorClient()
    result = client.get(collection_name=JIRA_COLLECTION)
    if not result or not result.ids[0]:
        print("Vector DB is empty.")
        return

    rows = list(zip(result.ids[0], result.documents[0], result.metadatas[0]))
    rows.sort(key=lambda r: (r[2] or {}).get("created", ""), reverse=True)

    lines = [""]
    for i, (_id, text, meta) in enumerate(rows, 1):
        meta = meta or {}
        summary, description = parse_ticket_text(text)
        lines.append(f"[{i}] Key: {meta.get('key', '')}")
        lines.append(f"Summary: {summary}")
        lines.append(f"Status: {meta.get('status', '')}")
        lines.append(f"Description: {description}")
        lines.append("")
        lines.append(SEPARATOR)

    OUTPUT.write_text("\n".join(lines))
    print(f"Wrote {len(rows)} tickets to {OUTPUT}")


if __name__ == "__main__":
    main()
