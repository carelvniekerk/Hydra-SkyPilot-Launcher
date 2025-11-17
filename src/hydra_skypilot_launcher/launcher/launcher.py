# coding=utf-8
# --------------------------------------------------------------------------------
# Project: Hydra SkyPilot Launcher
# Author: Carel van Niekerk
# Year: 2025
# Group: Dialogue Systems and Machine Learning Group
# Institution: Heinrich Heine University Düsseldorf
# --------------------------------------------------------------------------------
#
# This code was generated with the help of AI writing assistants
# including GitHub Copilot, ChatGPT, Bing Chat.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http: //www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Launcher Class."""

import sys
from collections.abc import Sequence
from logging import getLogger
from pathlib import Path

from hydra.core.utils import JobReturn, JobStatus
from hydra.plugins.launcher import Launcher
from hydra.types import HydraContext, TaskFunction
from omegaconf import DictConfig, OmegaConf

from hydra_skypilot_launcher.config.config_types import (
    FileMount,
    ResourcesConfig,
    TaskConfig,
)

__all__ = ["SkyPilotLauncher"]

logger = getLogger("HydraSkyPilotLauncher")


class SkyPilotLauncher(Launcher):
    """SkyPilot Launcher for Hydra."""

    def __init__(
        self,
        resources: ResourcesConfig,
        file_mounts: list[FileMount] | None = None,
        env_vars: dict[str, str] | None = None,
        setup_commands: list[str] | None = None,
    ) -> None:
        """Initialize the SkyPilot Launcher."""
        self.resources: ResourcesConfig = OmegaConf.to_object(resources)
        self.file_mounts: list[FileMount] = file_mounts or []
        self.env_vars: dict[str, str] = env_vars or {}
        self.setup_commands = setup_commands

    def setup(
        self,
        config: DictConfig,
        task_function: TaskFunction,
        hydra_context: HydraContext,
    ) -> None:
        """Set up the HPC Submission Launcher."""
        self.task_function: TaskFunction = task_function
        self.config = config
        self.hydra_context = hydra_context

    def launch(
        self,
        job_overrides: Sequence[Sequence[str]],
        initial_job_idx: int = 0,
    ) -> Sequence[JobReturn]:
        """Launch the jobs with the given overrides."""
        results: list[JobReturn] = []
        for idx, job_override in enumerate(job_overrides):
            job_idx = initial_job_idx + idx
            job_name: str = f"job_{job_idx}"
            job_script: str = " ".join(sys.argv)
            work_dir: Path = Path.cwd()

            task_config: TaskConfig = TaskConfig(
                name=job_name,
                resources=self.resources,
                workdir=work_dir,
                file_mounts=self.file_mounts,
                env_vars=self.env_vars,
                setup_commands=self.setup_commands,
                run_commands=job_script,
            )
            skypilot_task = task_config.to_sky_task()  # noqa: F841

            # Get the sweeper configuration
            sweep_config = self.hydra_context.config_loader.load_sweep_config(
                self.config,
                list(job_override),
            )

            results.append(
                JobReturn(
                    overrides=job_override,
                    status=JobStatus.COMPLETED,
                    cfg=sweep_config,
                ),
            )

        return results
