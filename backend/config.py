from hydra import compose, initialize_config_dir
from omegaconf import DictConfig, OmegaConf
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

_cfg: DictConfig = None
CONF_DIR = str(Path(__file__).parent.parent / "conf")


def load_config(overrides: list = None) -> DictConfig:
    global _cfg
    if _cfg is not None:
        return _cfg
    overrides = overrides or []
    with initialize_config_dir(config_dir=CONF_DIR, job_name="expense_tracker", version_base="1.3"):
        _cfg = compose(config_name="config", overrides=overrides)
    logger.info(f"Config loaded — model: {_cfg.model.model_id} | whisper: {_cfg.whisper.model_size}")
    return _cfg


def get_config() -> DictConfig:
    return load_config()


def config_to_dict(cfg: DictConfig) -> dict:
    return OmegaConf.to_container(cfg, resolve=True)
