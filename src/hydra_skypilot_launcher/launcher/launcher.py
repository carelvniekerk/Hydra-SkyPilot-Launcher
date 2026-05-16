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
"""SkyPilotLauncher — Hydra launcher plugin backed by SkyPilot.

Each call to :meth:`SkyPilotLauncher.launch` iterates over the provided
Hydra sweep overrides, constructs a SkyPilot ``Task`` from the launcher
config, and submits it via either ``sky.jobs.launch`` (managed job with
automatic retries and fault recovery, the default) or ``sky.launch``
(direct cluster launch that tears down on completion), depending on
``is_managed_job``.  A ``JobReturn`` is recorded for Hydra's sweeper
bookkeeping and the per-job output directory and config YAML files are
written to disk before the function returns.
"""

import sys
from logging import getLogger
from pathlib import Path
from typing import Sequence

from hydra.core.utils import HydraConfig, JobReturn, JobStatus
from hydra.plugins.launcher import Launcher
from hydra.types import HydraContext, TaskFunction
from omegaconf import DictConfig, OmegaConf, open_dict
from sky import launch as launch_direct_job
from sky.jobs import launch as launch_managed_job

from hydra_skypilot_launcher.config.config_types import (
    FileMount,
    ResourcesConfig,
    TaskConfig,
)
from hydra_skypilot_launcher.config.handler import handle_output_dir_and_save_configs

__all__ = ["SkyPilotLauncher"]

logger = getLogger("HydraSkyPilotLauncher")


class SkyPilotLauncher(Launcher):
    """Hydra ``Launcher`` plugin that submits sweep jobs via SkyPilot.

    Instantiated by Hydra from
    :class:`~hydra_skypilot_launcher.config.launcher.SkyPilotLauncherConfig`.
    Each sweep job becomes a SkyPilot managed job that runs on the requested
    cloud infrastructure with automatic provisioning and fault tolerance.
    """

    def __init__(  # noqa: PLR0913
        self,
        resources: ResourcesConfig,
        file_mounts: list[FileMount] | None = None,
        env_vars: dict[str, str] | None = None,
        secrets: dict[str, str] | None = None,
        setup_commands: list[str] | None = None,
        job_name_keys: list[str] | None = None,
        *,
        is_managed_job: bool = True,
        retry_until_up: bool = True,
    ) -> None:
        """Store launcher config, converting OmegaConf nodes to plain Python objects.

        Args:
            resources: Cloud resource requirements for every submitted job.
            file_mounts: Cloud storage volumes to attach to each job.
                Defaults to an empty list.
            env_vars: Non-sensitive runtime environment variables.
                Defaults to an empty dict.
            secrets: Secret environment variables passed securely to each job.
                Defaults to an empty dict.
            setup_commands: Shell commands run once when the cluster is first
                provisioned.  ``None`` skips the setup step.
            job_name_keys: List of config keys to include in the job name.
                Defaults to an empty list (only the task function name and
                job index are used).
            is_managed_job: If ``True``, the job is launched by a jobs controller
                instance that handles retries and failure recovery; if ``False``, the
                job is launched directly by the sweep launcher.  Defaults to ``True``.
            retry_until_up: If ``True``, the launcher will retry failed job launches
                indefinitely until they succeed.  Only applicable when
                ``is_managed_job=False``.  Defaults to ``True``.

        """
        self.resources: ResourcesConfig = OmegaConf.to_object(resources)  # ty:ignore[invalid-assignment]
        self.file_mounts: list[FileMount] = OmegaConf.to_object(file_mounts) or []  # ty:ignore[invalid-assignment]
        self.env_vars: dict[str, str] = OmegaConf.to_object(env_vars) or {}  # ty:ignore[invalid-assignment]
        self.secrets: dict[str, str] = OmegaConf.to_object(secrets) or {}  # ty:ignore[invalid-assignment]
        self.setup_commands: list[str] | None = OmegaConf.to_object(setup_commands)  # ty:ignore[invalid-assignment]
        self.job_name_keys: list[str] = OmegaConf.to_object(job_name_keys) or []  # ty:ignore[invalid-assignment]
        self.is_managed_job: bool = is_managed_job
        self.retry_until_up: bool = retry_until_up

    def setup(
        self,
        config: DictConfig,
        task_function: TaskFunction,
        hydra_context: HydraContext,
    ) -> None:
        """Bind the launcher to the current Hydra run context.

        Called by Hydra before :meth:`launch`.  Stores the task function,
        base config, and hydra context for use when constructing each job.

        Args:
            config: The base application config for this sweep.
            task_function: The user's task function (used to derive the job
                name via ``__name__``).
            hydra_context: Hydra context providing access to the config
                loader and other runtime utilities.

        """
        self.task_function: TaskFunction = task_function
        self.config = config
        self.hydra_context = hydra_context

    def _get_job_name(self, initial_job_idx: int, idx: int, config: DictConfig) -> str:
        """Build a unique job name for the SkyPilot managed job.

        When ``job_name_keys`` is configured, the name is built by joining the
        resolved config values at each key with underscores, followed by the
        global job index — e.g. ``"grpo_Qwen2.5-7B_MultiArith_0"``.  Nested
        keys (e.g. ``"trainer.name"``) are resolved via :func:`OmegaConf.select`.
        Keys that are missing or ``None`` in the config are silently skipped.

        When ``job_name_keys`` is empty the name falls back to the task
        function name suffixed with the global index —
        e.g. ``"<task_function_name>_<global_idx>"``.

        Args:
            initial_job_idx: Starting offset for job indices in this sweep
                batch (provided by Hydra's sweeper).
            idx: Position of the current job within the current batch.
            config: The fully resolved per-job sweep config, used to extract
                values when ``job_name_keys`` is set.

        Returns:
            A unique job name string of the form
            ``"<key_values...>_<global_idx>"`` or
            ``"<task_function_name>_<global_idx>"``.

        """
        if not self.job_name_keys:
            try:
                job_name: str = (
                    f"{self.task_function.func.__name__}_{initial_job_idx + idx}"  # ty:ignore[unresolved-attribute]
                )
            except AttributeError:
                job_name = f"{self.task_function.__name__}_{initial_job_idx + idx}"  # ty:ignore[unresolved-attribute]
            return job_name

        job_name_values: list[str] = []
        for key in self.job_name_keys:
            value = OmegaConf.select(config, key)
            if value is not None:
                job_name_values.append(value)
        job_name_values.append(str(initial_job_idx + idx))

        job_name: str = "_".join(job_name_values)
        return job_name.replace("/", "_")

    def _get_job_script(self, job_override: Sequence[str]) -> Path:
        """Determine the Python script that the remote job should execute.

        Defaults to ``sys.argv[0]`` (the script that launched the sweep).
        If a ``+launch.script=<path>`` override is present it is used instead
        and removed from ``job_override`` in-place.  When the resolved script
        lives in a ``bin/`` directory (i.e. an installed console script) only
        the bare name is kept so ``uv run`` can locate it by entry-point name.

        Args:
            job_override: Mutable sequence of Hydra override strings for this
                job.  Any ``+launch.script`` entry is consumed here.

        Returns:
            Path to the script or entry-point that the remote job will run.

        """
        job_script: Path = Path(sys.argv[0])
        if any("+launch.script=" in arg for arg in job_override):
            job_script = Path(
                next(arg for arg in job_override if "+launch.script=" in arg).split(
                    "=",
                    1,
                )[1],
            )
            job_override.pop(  # ty:ignore[unresolved-attribute]
                job_override.index(
                    next(arg for arg in job_override if "+launch.script=" in arg),
                ),
            )
        if job_script.suffix == "" and job_script.resolve().parent.name == "bin":
            job_script = Path(job_script.name)
        return job_script

    def _format_overrides(self, job_override: Sequence[str]) -> list[str]:
        """Escape and reformat Hydra overrides for safe shell embedding.

        Handles three categories of override:
        - Plain overrides (no special characters) are passed through unchanged.
        - Overrides containing backslashes, ``$``, or shell metacharacters
          (``(``, ``)``, ``{``, ``}``) are shell-escaped so they survive
          double-quoting inside the remote run command.
        - Overrides prefixed with ``+launch.*`` are separated from the Hydra
          overrides with a ``--`` sentinel and appended as positional arguments
          passed to the launched script rather than to Hydra. Within a launch
          override key, the literal ``PLUS_`` is rewritten to ``+`` so callers
          can express Hydra's add-key sigil (``+foo=bar``) on the launched
          script — the bare ``+`` cannot be used here because Hydra's CLI
          parser would consume it before the launcher sees the override.

        Args:
            job_override: Sequence of raw Hydra override strings for this job.

        Returns:
            A list of formatted override strings, with an optional ``"--"``
            separator followed by launch-command overrides at the end.

        """
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
                override_key = override_key.replace("PLUS_", "+")
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
        r"""Build the multi-line shell run command for the SkyPilot task.

        Combines the resolved job script and formatted overrides into a
        ``uv run <script> \\`` block where each override is indented on its
        own line for readability in SkyPilot logs.

        Args:
            job_override: Sequence of raw Hydra override strings for this job.

        Returns:
            A list of shell command lines that together form the run command.
            The first element is the ``uv run <script>`` invocation; subsequent
            elements are the indented, escaped override arguments.

        """
        job_script: Path = self._get_job_script(job_override)
        overrides_list: list[str] = self._format_overrides(job_override)
        overrides_list = [f"\t{override} \\" for override in overrides_list]
        if overrides_list:
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
        """Submit each sweep job as a SkyPilot managed job and return results.

        For every set of overrides in ``job_overrides`` this method:

        1. Derives a unique job name and run command.
        2. Constructs a :class:`~hydra_skypilot_launcher.config.config_types.TaskConfig`
           from the launcher's shared config and the per-job run command.
        3. Submits the task via ``sky.jobs.launch`` and records the request ID.
        4. Resolves the Hydra output directory and writes all config YAML files.
        5. Appends a ``JobReturn`` with status ``COMPLETED`` to the results.

        Args:
            job_overrides: Sequence of override lists, one per sweep job.
            initial_job_idx: Starting index offset for job naming, provided
                by Hydra's sweeper when batching jobs. Defaults to ``0``.

        Returns:
            A sequence of :class:`hydra.core.utils.JobReturn` objects, one per
            submitted job, each with status ``COMPLETED``.

        """
        results: list[JobReturn] = []
        for idx, job_override in enumerate(job_overrides):
            # Get the sweeper configuration
            sweep_config: DictConfig = (
                self.hydra_context.config_loader.load_sweep_config(
                    self.config,
                    list(job_override),
                )
            )
            job_name: str = self._get_job_name(initial_job_idx, idx, sweep_config)
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
            if self.is_managed_job:
                request_id = launch_managed_job(skypilot_task)
            else:
                request_id = launch_direct_job(
                    task=skypilot_task,
                    cluster_name=job_name,
                    down=True,
                    retry_until_up=self.retry_until_up,
                )
            logger.info(f"Job '{job_name}' launched successfully.")  # noqa: G004

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
