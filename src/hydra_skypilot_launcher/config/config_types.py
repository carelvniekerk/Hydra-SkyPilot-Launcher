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
"""Configuration dataclasses for Hydra SkyPilot Launcher."""

from dataclasses import dataclass, field
from pathlib import Path

from sky.data.storage import Storage, StorageMode, StoreType
from sky.resources import Resources
from sky.task import Task

__all__ = [
    "FileMount",
    "ResourcesConfig",
    "TaskConfig",
]


@dataclass
class FileMount:
    """File mount configuration."""

    name: str
    source: Path
    destination: Path
    store: StoreType | None = None
    mode: StorageMode = StorageMode.MOUNT
    persistent: bool = True

    def to_sky_storage(self) -> Storage:
        """Convert to dictionary representation."""
        storage = Storage(
            name=self.name,
            source=self.source.as_posix(),
            stores=[self.store] if self.store else None,  # type: ignore[invalid-argument-type]
            mode=self.mode,
            persistent=self.persistent,
        )
        return storage


@dataclass
class ResourcesConfig:
    """Resources configuration dataclass."""

    infrastructure: str
    cpus: int | str | None = None
    memory: int | str | None = None
    accelerators: str | None = None
    disk_size: int | str | None = None
    use_spot: bool = False

    def to_sky_resources(self) -> Resources:
        """Convert to SkyPilot Resources object."""
        return Resources(
            infra=self.infrastructure,
            cpus=self.cpus,
            memory=self.memory,
            accelerators=self.accelerators,
            disk_size=self.disk_size,
            use_spot=self.use_spot,
        )


@dataclass
class TaskConfig:
    """Task configuration dataclass."""

    name: str
    resources: ResourcesConfig
    workdir: Path | None = None
    file_mounts: list[FileMount] = field(default_factory=list)
    env_vars: dict[str, str] = field(default_factory=dict)
    secrets: dict[str, str] = field(default_factory=dict)
    setup_commands: str | list[str] | None = None
    run_commands: str | list[str] | None = None

    def to_sky_task(self) -> Task:
        """Convert to SkyPilot Task object."""
        return Task(
            name=self.name,
            resources=self.resources.to_sky_resources(),
            workdir=self.workdir.as_posix() if self.workdir else None,
            storage_mounts={
                fm.destination.as_posix(): fm.to_sky_storage()
                for fm in self.file_mounts
            },
            envs=self.env_vars,
            secrets=self.secrets,
            setup=self.setup_commands,
            run=self.run_commands,
        )
