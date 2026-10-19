"""Shallow clone the prd catalogs into branch-specific catalogs via a SQL warehouse.

Branch DATA-311 gets data_311_raw (from prd_raw) and data_311_staging (from prd_staging).
Auth comes from the standard DATABRICKS_* env vars or your local Databricks CLI profile.

    python scripts/clone_catalogs.py --branch DATA-311
"""

import argparse
import os
import re

from databricks import sql
from databricks.sdk.core import Config

# Source catalog -> suffix of the branch catalog
SOURCE_CATALOGS = {"prd_raw": "raw", "prd_staging": "staging"}


def branch_catalog_name(branch: str, suffix: str) -> str:
    """Turn a git branch name into a valid Unity Catalog name, e.g. DATA-311 -> data_311_raw."""
    base = re.sub(r"[^a-z0-9]+", "_", branch.lower()).strip("_")
    if not base:
        raise ValueError(f"Branch name {branch!r} gives an empty catalog name")
    return f"{base}_{suffix}"


def clone_catalog(cur, src_cat: str, dst_cat: str) -> list[tuple]:
    """Shallow clone every managed Delta table of src_cat into dst_cat; return what was skipped."""
    cur.execute(f"CREATE CATALOG IF NOT EXISTS `{dst_cat}`")

    # Schemas (skip information_schema)
    cur.execute(f"""
        SELECT schema_name FROM `{src_cat}`.information_schema.schemata
        WHERE schema_name <> 'information_schema'
    """)
    schemas = [r.schema_name for r in cur.fetchall()]

    for s in schemas:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS `{dst_cat}`.`{s}`")

    # Tables
    cur.execute(f"""
        SELECT table_schema, table_name, table_type, data_source_format
        FROM `{src_cat}`.information_schema.tables
        WHERE table_schema <> 'information_schema'
    """)
    tables = cur.fetchall()

    skipped = []
    for t in tables:
        fqn_src = f"`{src_cat}`.`{t.table_schema}`.`{t.table_name}`"
        fqn_dst = f"`{dst_cat}`.`{t.table_schema}`.`{t.table_name}`"

        if t.table_type == "MANAGED" and t.data_source_format == "DELTA":
            print(f"  {fqn_src} -> {fqn_dst}")
            cur.execute(f"CREATE OR REPLACE TABLE {fqn_dst} SHALLOW CLONE {fqn_src}")
        else:
            skipped.append((t.table_schema, t.table_name, t.table_type, t.data_source_format))

    return skipped


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", required=True)
    parser.add_argument("--warehouse-id", default=os.environ.get("DATABRICKS_WAREHOUSE_ID"))
    parser.add_argument("--profile", help="~/.databrickscfg profile (local runs)")
    args = parser.parse_args()
    if not args.warehouse_id:
        parser.error("--warehouse-id or DATABRICKS_WAREHOUSE_ID is required")

    cfg = Config(profile=args.profile)
    with sql.connect(
        server_hostname=cfg.host.removeprefix("https://"),
        http_path=f"/sql/1.0/warehouses/{args.warehouse_id}",
        credentials_provider=lambda: cfg.authenticate,
    ) as conn, conn.cursor() as cur:
        for src_cat, suffix in SOURCE_CATALOGS.items():
            dst_cat = branch_catalog_name(args.branch, suffix)
            # Never clone onto a production catalog (e.g. a branch called "prd")
            if dst_cat in SOURCE_CATALOGS:
                raise ValueError(f"Refusing to clone into production catalog {dst_cat}")

            print(f"Cloning {src_cat} -> {dst_cat}")
            skipped = clone_catalog(cur, src_cat, dst_cat)

            print(f"Skipped in {src_cat} (handle separately):")
            for s in skipped:
                print(s)


if __name__ == "__main__":
    main()
