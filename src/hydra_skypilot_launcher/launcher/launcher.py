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
from logging import getLogger
from pathlib import Path
from typing import Sequence

from hydra.core.utils import HydraConfig, JobReturn, JobStatus
from hydra.plugins.launcher import Launcher
from hydra.types import HydraContext, TaskFunction
from omegaconf import DictConfig, OmegaConf, open_dict
from sky.jobs import launch

from hydra_skypilot_launcher.config.config_types import (
    FileMount,
    ResourcesConfig,
    TaskConfig,
)
from hydra_skypilot_launcher.config.handler import handle_output_dir_and_save_configs

__all__ = ["SkyPilotLauncher"]

logger = getLogger("HydraSkyPilotLauncher")


class SkyPilotLauncher(Launcher):
    """SkyPilot Launcher for Hydra."""

    def __init__(
        self,
        resources: ResourcesConfig,
        file_mounts: list[FileMount] | None = None,
        env_vars: dict[str, str] | None = None,
        secrets: dict[str, str] | None = None,
        setup_commands: list[str] | None = None,
    ) -> None:
        """Initialize the SkyPilot Launcher."""
        self.resources: ResourcesConfig = OmegaConf.to_object(resources)
        self.file_mounts: list[FileMount] = OmegaConf.to_object(file_mounts) or []
        self.env_vars: dict[str, str] = OmegaConf.to_object(env_vars) or {}
        self.secrets: dict[str, str] = OmegaConf.to_object(secrets) or {}
        self.setup_commands: list[str] | None = OmegaConf.to_object(setup_commands)

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

    def _get_job_name(self, initial_job_idx: int, idx: int) -> str:
        """Get the job name based on the task function name and job index."""
        try:
            job_name: str = (
                f"{self.task_function.func.__name__}_{initial_job_idx + idx}"  # type: ignore[attr-defined]
            )
        except AttributeError:
            job_name = f"{self.task_function.__name__}_{initial_job_idx + idx}"
        return job_name

    def _get_job_script(self, job_override: Sequence[str]) -> Path:
        """Get the job script path."""
        job_script: Path = Path(sys.argv[0])
        if any("+launch.script=" in arg for arg in job_override):
            job_script = Path(
                next(arg for arg in job_override if "+launch.script=" in arg).split(
                    "=",
                    1,
                )[1],
            )
            job_override.pop(  # type: ignore[unresolved-attribute]
                job_override.index(
                    next(arg for arg in job_override if "+launch.script=" in arg),
                ),
            )
        if job_script.suffix == "" and job_script.resolve().parent.name == "bin":
            job_script = Path(job_script.name)
        return job_script

    def _format_overrides(self, job_override: Sequence[str]) -> list[str]:
        """Format the overrides for command line usage."""
        # Reformat string overrides to handle spaces in the values
        overrides_list: list[str] = []
        launch_command_overrides: list[str] = []
        for override in job_override:
            if (
                "\\" not in override
                and "$" not in override
                and "+launch" not in override
            ):
                overrides_list.append(override)
                continue

            override_key, override_value = override.split("=", 1)
            override_value = override_value.replace("\\", "")

            if "(" in override_value:
                override_value = override_value.replace("(", "\\(")
            if ")" in override_value:
                override_value = override_value.replace(")", "\\)")
            if "{" in override_value:
                override_value = override_value.replace("{", "\\{")
            if "}" in override_value:
                override_value = override_value.replace("}", "\\}")
            if "$" in override_value:
                override_value = override_value.replace("$", "\\\\\\\\$")

            # Handle launch command overrides
            if "+launch" in override_key:
                override_key = override_key.replace("+launch.", "").replace(
                    "+launch/",
                    "",
                )
                launch_command_overrides.append(
                    f'{override_key}=\\"{override_value}\\"',
                )
                continue
            overrides_list.append(f'{override_key}=\\"{override_value}\\"')

        if launch_command_overrides:
            overrides_list.append("--")
            overrides_list.extend(launch_command_overrides)
        return overrides_list

    def _get_run_command(self, job_override: Sequence[str]) -> list[str]:
        """Get the run command for the job."""
        job_script: Path = self._get_job_script(job_override)
        overrides_list: list[str] = self._format_overrides(job_override)
        overrides_list = [f"\t{override} \\" for override in overrides_list]
        overrides_list[-1] = overrides_list[-1].rstrip(" \\")
        job_script_str = f"uv run {job_script.as_posix()}"
        job_script_str += " \\" if overrides_list else ""
        run_command: list[str] = [job_script_str, *overrides_list]
        return run_command

    def launch(
        self,
        job_overrides: Sequence[Sequence[str]],
        initial_job_idx: int = 0,
    ) -> Sequence[JobReturn]:
        """Launch the jobs with the given overrides."""
        results: list[JobReturn] = []
        for idx, job_override in enumerate(job_overrides):
            job_name: str = self._get_job_name(initial_job_idx, idx)
            run_command: list[str] = self._get_run_command(job_override)
            work_dir: Path = Path.cwd()

            task_config: TaskConfig = TaskConfig(
                name=job_name,
                resources=self.resources,
                workdir=work_dir,
                file_mounts=self.file_mounts,
                env_vars=self.env_vars,
                secrets=self.secrets,
                setup_commands=self.setup_commands,
                run_commands=run_command,
            )
            skypilot_task = task_config.to_sky_task()
            sky_config_dict = skypilot_task.to_yaml_config(use_user_specified_yaml=True)
            sky_config: DictConfig = OmegaConf.create(sky_config_dict)

            # Launch the job using SkyPilot
            logger.info(f"Launching job '{job_name}' with SkyPilot...")  # noqa: G004
            logger.info(f"Run command: {' '.join(run_command)}")  # noqa: G004
            request_id = launch(skypilot_task)
            logger.info(f"Job '{job_name}' launched successfully.")  # noqa: G004

            # Get the sweeper configuration
            sweep_config = self.hydra_context.config_loader.load_sweep_config(
                self.config,
                list(job_override),
            )
            with open_dict(sweep_config):
                # Assign HPC job id to the sweep configuration
                sweep_config.hydra.job.id = request_id
            HydraConfig.instance().set_config(sweep_config)

            handle_output_dir_and_save_configs(
                hydra_config=sweep_config,
                sky_config=sky_config,
            )

            results.append(
                JobReturn(
                    overrides=job_override,
                    status=JobStatus.COMPLETED,
                    cfg=sweep_config,
                ),
            )

        return results
