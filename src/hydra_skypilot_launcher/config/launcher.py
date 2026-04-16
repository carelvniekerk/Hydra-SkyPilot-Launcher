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
"""Hydra structured config for the SkyPilot launcher plugin.

Defines :class:`SkyPilotLauncherConfig` as the Hydra structured config node
that configures the launcher.  This dataclass is registered as the launcher's
config schema and drives instantiation of
:class:`~hydra_skypilot_launcher.launcher.SkyPilotLauncher`.
"""

from dataclasses import dataclass, field

from hydra_skypilot_launcher.config.config_types import (
    FileMount,
    ResourcesConfig,
)


@dataclass
class SkyPilotLauncherConfig:
    """Hydra structured config schema for the SkyPilot launcher.

    All fields map directly to the constructor parameters of
    :class:`~hydra_skypilot_launcher.launcher.SkyPilotLauncher`.

    Attributes:
        resources: Cloud resource requirements shared by every sweep job.
        _target_: Hydra instantiation target; must not be overridden.
        file_mounts: Cloud storage volumes attached to each job.
        env_vars: Non-sensitive environment variables injected at runtime.
        secrets: Secret environment variables passed via SkyPilot's secrets
            mechanism and redacted from saved configs.
        setup_commands: Shell commands run once during cluster provisioning.
        job_name_keys: List of config keys to use for naming jobs.  If empty,
            jobs are named using the task function name and job index.

    """

    resources: ResourcesConfig
    _target_: str = "hydra_skypilot_launcher.launcher.SkyPilotLauncher"
    file_mounts: list[FileMount] = field(default_factory=list)
    env_vars: dict[str, str] = field(default_factory=dict)
    secrets: dict[str, str] = field(default_factory=dict)
    setup_commands: list[str] | None = None
    job_name_keys: list[str] = field(default_factory=list)
