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
"""Configuration for the Hydra SkyPilot Launcher."""

from dataclasses import dataclass, field

from hydra_skypilot_launcher.config.config_types import (
    FileMount,
    ResourcesConfig,
)


@dataclass
class SkyPilotLauncherConfig:
    """Configuration for HPC submission launcher."""

    resources: ResourcesConfig
    _target_: str = "hydra_skypilot_launcher.launcher.SkyPilotLauncher"
    file_mounts: list[FileMount] = field(default_factory=list)
    env_vars: dict[str, str] = field(default_factory=dict)
    setup_commands: list[str] | None = None
