# hello_bundle

Minimal Databricks Asset Bundle: one Python wheel job running on serverless compute,
unit tests, and GitHub Actions CI/CD.

```
src/hello_bundle/      Python package (built into a wheel)
  main.py              job entry point (Spark)
  transforms.py        pure-Python logic, unit tested without Spark
tests/                 pytest unit tests
resources/hello_job.yml  job definition (serverless, daily 06:00 Brussels, paused)
databricks.yml         buprod targets
.github/workflows/     ci.yml (PRs) and deploy.yml (main -> prod)
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
4. If people other than the SP need to see or trigger the prod job, grant them permissions on the job
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
