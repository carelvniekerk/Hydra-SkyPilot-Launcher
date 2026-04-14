# coding=utf-8
# --------------------------------------------------------------------------------
# Project: Hydra SkyPilot Launcher
# Author: Carel van Niekerk
# Year: 2026
# --------------------------------------------------------------------------------
#
# This code was generated with the help of AI writing assistants
# including GitHub Copilot, ChatGPT Codex, Claude Code, Gemini.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Output directory management and config persistence for sweep jobs.

Resolves the per-job output directory from the Hydra sweep configuration,
creates it on disk, and saves all relevant configs (``config.yaml``,
``hydra.yaml``, ``overrides.yaml``, ``sky_job.yaml``) into the Hydra output
subdirectory.  Secrets stored in the launcher config are redacted before
writing.
"""

from pathlib import Path

from hydra.core.hydra_config import HydraConf, HydraConfig
from hydra.core.utils import _save_config
from omegaconf import DictConfig, OmegaConf, open_dict

__all__ = ["handle_output_dir_and_save_configs"]


def handle_output_dir_and_save_configs(
    hydra_config: DictConfig,
    sky_config: DictConfig,
    job_dir_key: str = "hydra.sweep.dir",
    job_subdir_key: str = "hydra.sweep.subdir",
) -> None:
    """Resolve the job output directory and persist all sweep configs to disk.

    Temporarily activates ``hydra_config`` as the live Hydra config so that
    OmegaConf interpolations (e.g. ``${hydra.job.num}``) in the sweep dir
    path resolve correctly.  After resolving, the output directory is created
    and four YAML files are written into the Hydra output subdirectory:
    ``config.yaml``, ``hydra.yaml``, ``overrides.yaml``, and
    ``sky_job.yaml``.  Any secrets in the launcher config are replaced with
    ``"<redacted>"`` before writing.

    Args:
        hydra_config: The per-job Hydra sweep config containing sweep dir,
            subdir, and launcher settings.
        sky_config: The SkyPilot job YAML config produced from the task,
            saved as ``sky_job.yaml`` for reference.
        job_dir_key: OmegaConf dotpath to the sweep base directory within
            ``hydra_config``. Defaults to ``"hydra.sweep.dir"``.
        job_subdir_key: OmegaConf dotpath to the per-job subdirectory within
            ``hydra_config``. Defaults to ``"hydra.sweep.subdir"``.

    """
    orig_hydra_cfg = HydraConfig.instance().cfg

    # init Hydra config for config evaluation
    HydraConfig.instance().set_config(hydra_config)

    output_dir: Path = Path(OmegaConf.select(hydra_config, job_dir_key))
    if job_subdir_key is not None:
        subdir = Path(OmegaConf.select(hydra_config, job_subdir_key))
        output_dir = output_dir / subdir

    # Temporarily allow modification of the read-only config
    with open_dict(hydra_config):
        OmegaConf.set_readonly(hydra_config.hydra.runtime, value=False)
        hydra_config.hydra.runtime.output_dir = output_dir.resolve()
        OmegaConf.set_readonly(hydra_config.hydra.runtime, value=True)

    # update Hydra config
    HydraConfig.instance().set_config(hydra_config)

    try:
        # handle output directories here
        Path(str(output_dir)).mkdir(parents=True, exist_ok=True)

        if hydra_config.hydra.output_subdir is not None:
            hydra_output = Path(hydra_config.hydra.runtime.output_dir) / Path(
                hydra_config.hydra.output_subdir,
            )

            # Redact secrets before saving configs
            cfg_instance: HydraConf = HydraConfig.instance().cfg  # ty:ignore[invalid-assignment]
            OmegaConf.set_readonly(hydra_config.hydra.launcher.secrets, value=False)
            OmegaConf.set_readonly(cfg_instance.hydra.launcher.secrets, value=False)  # ty:ignore[unresolved-attribute]
            for key in hydra_config.hydra.launcher.secrets:
                setattr(hydra_config.hydra.launcher.secrets, key, "<redacted>")
                setattr(cfg_instance.hydra.launcher.secrets, key, "<redacted>")  # ty:ignore[unresolved-attribute]
            OmegaConf.set_readonly(hydra_config.hydra.launcher.secrets, value=True)
            OmegaConf.set_readonly(cfg_instance.hydra.launcher.secrets, value=True)  # ty:ignore[unresolved-attribute]

            _save_config(hydra_config, "config.yaml", hydra_output)
            _save_config(cfg_instance, "hydra.yaml", hydra_output)  # type: ignore  # noqa: PGH003
            _save_config(
                cfg=hydra_config.hydra.overrides.task,
                filename="overrides.yaml",
                output_dir=hydra_output,
            )
            _save_config(sky_config, "sky_job.yaml", hydra_output)
    finally:
        HydraConfig.instance().cfg = orig_hydra_cfg
