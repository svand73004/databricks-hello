# hello_bundle

Minimal Databricks bundle: one Python wheel job, unit tests, GitHub Actions CI/CD.

## Local development
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
export BUNDLE_VAR_host=https://<your-workspace>.cloud.databricks.com
databricks auth login --host $BUNDLE_VAR_host
databricks bundle validate -t dev
databricks bundle deploy -t dev
databricks bundle run hello_job -t dev
```

## CI/CD
- PR -> `ci.yml`: ruff, pytest, `bundle validate`
- merge to main -> `deploy.yml`: pytest, `bundle deploy -t prod`

Repo secrets: DATABRICKS_HOST, DATABRICKS_CLIENT_ID, DATABRICKS_CLIENT_SECRET
(OAuth M2M credentials of a service principal).
