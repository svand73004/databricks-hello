import pytest
from clone_catalogs import branch_catalog_name


def test_branch_catalog_name():
    assert branch_catalog_name("DATA-311", "raw") == "data_311_raw"
    assert branch_catalog_name("feature/DATA-311-new.thing", "staging") == "feature_data_311_new_thing_staging"


def test_branch_catalog_name_empty():
    with pytest.raises(ValueError):
        branch_catalog_name("--", "raw")
