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

from collections.abc import Sequence
from logging import getLogger

from hydra.core.utils import JobReturn, JobStatus
from hydra.plugins.launcher import Launcher
from hydra.types import HydraContext, TaskFunction
from omegaconf import DictConfig

__all__ = ["SkyPilotLauncher"]

logger = getLogger("HydraSkyPilotLauncher")


class SkyPilotLauncher(Launcher):
    """SkyPilot Launcher for Hydra."""

    def setup(
        self,
        config: DictConfig,
        task_function: TaskFunction,
        hydra_context: HydraContext,
    ) -> None:
        """Set up the HPC Submission Launcher."""
        self.task_function = task_function
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
            job_idx = initial_job_idx + idx  # noqa: F841
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
