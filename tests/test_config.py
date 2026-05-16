from pathlib import Path

from quant_data.config import load_config, project_root, resolve_path


def test_project_root_points_to_repository_root():
    root = project_root()

    assert (root / "pyproject.toml").exists()
    assert root.name == "量化项目"


def test_load_config_reads_data_yaml():
    config = load_config("configs/data.yaml")

    assert config["paths"]["ods_dir"] == "data/ods"
    assert config["cleaning"]["abnormal_return_threshold"] == 0.2


def test_resolve_path_uses_project_root():
    path = resolve_path("data/dwd")

    assert path == project_root() / Path("data/dwd")
