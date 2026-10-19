# hello_bundle

Minimal Databricks Asset Bundle: one Python wheel job running on serverless compute,
unit tests, and GitHub Actions CI/CD.

```
src/hello_bundle/      Python package (built into a wheel)
  main.py              job entry point (Spark)
  transforms.py        pure-Python logic, unit tested without Spark
  weather_api.py       Open-Meteo API client + parsing (unit tested)
  weather_job.py       weather job entry point: MERGE into a Delta table
tests/                 pytest unit tests
resources/hello_job.yml  job definition (serverless, daily 06:00 Brussels, paused)
resources/weather_job.yml  weather job: ingest + MERGE, then refresh the pipeline (daily 07:00, paused)
resources/weather_pipeline.yml  Lakeflow Declarative Pipeline (serverless) for monthly stats
pipelines/monthly_weather.py    pipeline source: monthly_weather_per_city materialized view
resources/weather_pipeline_sql.yml  same pipeline, SQL-only version
pipelines/monthly_weather.sql   pipeline source: monthly_weather_per_city_sql materialized view
databricks.yml         buprod targets
scripts/clone_catalogs.py  shallow clones prd_raw / prd_staging into per-branch catalogs
.github/workflows/     ci.yml (PRs), deploy.yml (main -> prod), branch-catalogs.yml (new branch -> catalogs)
```

## 1. Install locally

| Tool | Why | Install (macOS) |
|------|-----|-----------------|
| Python 3.10+ (3.11 recommended, same as CI) | run tests (uv can also install it: `uv python install 3.11`) | `brew install python@3.11` |
| [uv](https://docs.astral.sh/uv/) | manages the virtualenv/dependencies, and the bundle builds the wheel with `uv build --wheel` | `brew install uv` |
| [Databricks CLI](https://docs.databricks.com/dev-tools/cli/install.html) v0.218+ | validate / deploy / run the bundle | `brew tap databricks/tap && brew install databricks` |
| git + a GitHub account | CI/CD | `brew install git` |

Check: `databricks --version`, `uv --version`.

Linux/Windows: see the linked install pages (`curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh` works on Linux/WSL).

## 2. Prepare the Databricks workspace

You need a Databricks workspace (AWS, Azure or GCP) with:

1. **Unity Catalog** enabled (default for new workspaces).
2. **Serverless compute for jobs** enabled — the job uses an `environments` spec instead of a cluster.
   Account console → *Settings* → *Feature enablement* (enabled by default in most regions).
3. **A personal login for yourself** — used for the `dev` target.

### Service principal for prod / CI

The `prod` target is deployed by GitHub Actions and runs as a service principal (SP).

1. Workspace → *Settings* → *Identity and access* → *Service principals* → **Add service principal**
   (or create it in the account console and add it to the workspace).
2. Give it **Workspace access** (entitlement on the SP's *Configurations* tab).
3. On the SP's *Secrets* tab → **Generate secret**. Copy:
   - the **Client ID** (= Application ID, a UUID)
   - the **Secret** (shown only once)
4. Grant the SP rights to create the pipeline schema and tables (SQL editor, as catalog owner/admin):
   ```sql
   GRANT USE CATALOG, CREATE SCHEMA ON CATALOG workspace TO `<sp-client-id>`;
   ```
5. For the [branch catalogs](#branch-catalogs), also grant the SP:
   - `CAN USE` on SQL warehouse `d20c475e4924b5c9` (warehouse → *Permissions*)
   - `CREATE CATALOG` on the metastore (*Catalog* → gear icon → *Metastore* → *Permissions*)
   - read access to the prd catalogs:
     ```sql
     GRANT USE CATALOG, USE SCHEMA, SELECT ON CATALOG prd_raw     TO `<sp-client-id>`;
     GRANT USE CATALOG, USE SCHEMA, SELECT ON CATALOG prd_staging TO `<sp-client-id>`;
     ```
6. If people other than the SP need to see or trigger the prod job, grant them permissions on the job
   after the first deploy (or add a `permissions:` block to `databricks.yml`).

The SP deploys into its own folder (`/Workspace/Users/<sp-client-id>/.bundle/hello_bundle/prod`)
and is also the job's `run_as` identity, so no extra "Service principal: User" role is needed.
If you ever deploy prod as a different identity, that identity needs the **Service principal: User**
role on the SP.

## 3. Local development (dev target)

```bash
# Python env + tests (uv creates .venv and installs from uv.lock)
uv sync --extra dev
uv run ruff check .
uv run pytest

# Authenticate the CLI with your own user (opens a browser, stores a profile in ~/.databrickscfg)
databricks auth login --host https://<your-workspace>.cloud.databricks.com --profile dev

# Validate, deploy and run your private dev copy of the job
databricks bundle validate -t dev -p dev
databricks bundle deploy   -t dev -p dev
databricks bundle run hello_job -t dev -p dev

# Clean up
databricks bundle destroy -t dev -p dev
```

In `dev` (`mode: development`) the job is prefixed with `[dev <your name>]`, schedules are paused,
and the files go to your own user folder, so several developers can deploy side by side.

### Testing the prod target locally (optional)

To reproduce what CI does, use the SP credentials. Keep them in `.env` (gitignored, never commit it)
using the variable names the CLI expects:

```bash
# .env
DATABRICKS_HOST=https://<your-workspace>.cloud.databricks.com
DATABRICKS_CLIENT_ID=<sp-client-id>
DATABRICKS_CLIENT_SECRET=<sp-secret>
BUNDLE_VAR_prod_service_principal=<sp-client-id>
```

```bash
set -a && source .env && set +a
databricks bundle validate -t prod
```

## Weather pipeline

`weather_job` calls the free [Open-Meteo](https://open-meteo.com/) API (no API key) for a few
Belgian cities (`CITIES` in `weather_api.py`), takes the last 7 days plus a 7-day forecast, and
MERGEs it into `<catalog>.<schema>.daily_weather` on `(city, date)`:

- new days are inserted
- existing days are updated only when a value changed (forecasts get revised, and a forecast day
  becomes an actual day), and `updated_at` records when
- the schema and table are created on the first run

| Target | Table |
|--------|-------|
| dev | `workspace.weather_dev_<your-short-name>.daily_weather` |
| prod | `workspace.weather.daily_weather` |

After the MERGE, the job's second task refreshes `weather_pipeline`, a Lakeflow Declarative
Pipeline with one materialized view, `monthly_weather_per_city`: highest, lowest and average
temperature per city and month. Only actual days count; forecast days are left out. The average
is the mean of each day's (max + min) / 2. The view lives in the same schema as `daily_weather`.

`weather_pipeline_sql` does exactly the same in plain SQL (`pipelines/monthly_weather.sql`) and
writes `monthly_weather_per_city_sql`, so you can compare the Python and SQL styles. The job
refreshes both pipelines in parallel after the MERGE.

Override with `--var catalog=... --var schema=...` or in `databricks.yml`.

```bash
databricks bundle deploy -t dev -p dev
databricks bundle run weather_job -t dev -p dev
```

Then query it in the SQL editor:

```sql
SELECT * FROM workspace.weather_dev_<your-short-name>.daily_weather ORDER BY city, date;
SELECT * FROM workspace.weather_dev_<your-short-name>.monthly_weather_per_city ORDER BY city, month;
SELECT * FROM workspace.weather_dev_<your-short-name>.monthly_weather_per_city_sql ORDER BY city, month;
```

## Branch catalogs

Every new GitHub branch gets its own copy of the prd data, as
[shallow clones](https://docs.databricks.com/en/delta/clone.html) (metadata only, no data is copied):

| Branch | Catalogs created |
|--------|------------------|
| `DATA-311` | `data_311_raw` (from `prd_raw`), `data_311_staging` (from `prd_staging`) |
| `feature/DATA-311` | `feature_data_311_raw`, `feature_data_311_staging` |

The branch name is lowercased and anything that isn't a letter or digit becomes `_`.

How it works:

- `.github/workflows/branch-catalogs.yml` runs on GitHub's `create` event (branches only, not tags)
  and calls `scripts/clone_catalogs.py --branch <branch>`.
- The script runs plain SQL on SQL warehouse `d20c475e4924b5c9` (via `databricks-sql-connector`),
  using the same SP secrets as the other workflows. No bundle deploy or job is involved.
- It creates the catalog and every schema, then runs `CREATE OR REPLACE TABLE ... SHALLOW CLONE`
  for each **managed Delta** table. Views, external tables and other formats are skipped and listed
  in the workflow log: handle those separately.
- It refuses to write into `prd_raw` / `prd_staging` (e.g. for a branch called `prd`).
- Re-running it for the same branch re-clones every table from the current prd state, which
  **discards any changes** made to those tables in the branch catalog.

Notes:

- GitHub only runs the workflow once `branch-catalogs.yml` is on the default branch.
- Shallow clones point to the source table's files. If prd tables are `VACUUM`ed, old clones can
  break; re-run the script to refresh them.
- The catalogs are **not** dropped when the branch is deleted. Clean up manually:
  `DROP CATALOG data_311_raw CASCADE;`

Run it by hand (uses your local Databricks CLI login; this really creates the catalogs):

```bash
uv run --extra dev python scripts/clone_catalogs.py --branch DATA-311 --warehouse-id d20c475e4924b5c9 --profile dev
```

Make sure `DATABRICKS_HOST` is not set in your shell (`unset DATABRICKS_HOST`): it overrides the
profile, and a URL copied from the browser (`...cloud.databricks.com?o=123`) doesn't work.

To re-run it for an existing branch on GitHub, delete and re-push the branch, or run the command
above.

## 4. GitHub integration

### 4a. GitHub Actions (CI/CD — required)

1. Push this repo to GitHub.
2. Repo → *Settings* → *Secrets and variables* → *Actions* → **New repository secret**:

   | Secret | Value |
   |--------|-------|
   | `DATABRICKS_HOST` | `https://<your-workspace>.cloud.databricks.com` |
   | `DATABRICKS_CLIENT_ID` | SP client ID |
   | `DATABRICKS_CLIENT_SECRET` | SP OAuth secret |

3. Repo → *Settings* → *Environments* → **New environment** named `production`
   (`deploy.yml` uses it). Optionally add **Required reviewers** for a manual approval gate before
   prod deploys. You can also store the secrets on this environment instead of the repo, but then
   `ci.yml` (which has no environment) won't see them.
4. Recommended: *Settings* → *Branches* → protect `main` and require the `CI / test-and-validate`
   check to pass before merging.

Flow:

- **Pull request** → `ci.yml`: `ruff`, `pytest`, `databricks bundle validate -t prod`
- **Merge to `main`** → `deploy.yml`: `pytest`, `databricks bundle deploy -t prod`
- **New branch** → `branch-catalogs.yml`: shallow clone the prd catalogs (see [Branch catalogs](#branch-catalogs))

The prod job is deployed with its schedule **paused** (`pause_status: PAUSED` in
`resources/hello_job.yml`). Set it to `UNPAUSED` when you want it to run daily, or trigger it
manually from *Jobs & Pipelines* in the workspace.

Note: PRs from forks don't get repository secrets, so the validate step fails for them.

### 4b. Databricks Git folders (optional)

Only needed if you want to browse/edit this repo inside the Databricks UI:

1. Workspace → your user icon → *Settings* → *Linked accounts* → **Git integration** →
   provider *GitHub* → link via the Databricks GitHub App (or a GitHub personal access token).
2. *Workspace* → *Create* → **Git folder** → paste the repo URL.

The deployed job does not depend on this — it runs from the wheel uploaded by `bundle deploy`.

## Troubleshooting

- `uv: command not found` during deploy → install uv (the wheel build step needs it).
- `cannot resolve bundle auth configuration` → pass `-p <profile>` or set `DATABRICKS_HOST`.
- `run_as` / service principal errors on prod → `BUNDLE_VAR_prod_service_principal` must be the SP's
  **client ID**, not its display name.
- Job fails to start with a compute error → serverless jobs are not enabled for the workspace.
- Branch catalogs workflow fails with `PERMISSION_DENIED` → the SP is missing one of the grants in
  step 5 of the service principal setup (warehouse `CAN USE`, `CREATE CATALOG`, or read on prd).
- Branch catalogs workflow doesn't start → `branch-catalogs.yml` isn't on `main` yet, or the
  branch was created by another workflow using `GITHUB_TOKEN` (GitHub doesn't trigger workflows
  from those events).
