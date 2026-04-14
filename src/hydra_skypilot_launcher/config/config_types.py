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
"""Dataclasses representing SkyPilot job configuration primitives.

Defines :class:`FileMount`, :class:`ResourcesConfig`, and :class:`TaskConfig`,
each of which maps to the corresponding SkyPilot SDK object via a ``to_sky_*``
conversion method.  These types are used both as plain Python dataclasses and
as Hydra structured config nodes (instantiated via OmegaConf).
"""

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
    """A cloud storage mount attached to a SkyPilot task.

    Attributes:
        name: Unique name for the storage bucket or volume.
        source: Local or remote path to the data source.
        destination: Mount path inside the remote task container.
        store: Cloud store backend (e.g. S3, GCS). ``None`` lets SkyPilot
            infer the store from the source URI.
        mode: How the storage is surfaced — ``MOUNT`` streams on demand,
            ``COPY`` downloads upfront.
        persistent: If ``True`` the storage object persists after the task
            completes; if ``False`` it is cleaned up automatically.

    """

    name: str
    source: Path
    destination: Path
    store: StoreType | None = None
    mode: StorageMode = StorageMode.MOUNT
    persistent: bool = True

    def to_sky_storage(self) -> Storage:
        """Convert to a SkyPilot :class:`sky.data.storage.Storage` object.

        Returns:
            A configured ``Storage`` instance ready to be passed to a
            SkyPilot ``Task``.

        """
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
    """Cloud resource requirements for a SkyPilot task.

    Attributes:
        infrastructure: Target cloud and region, e.g. ``"aws/us-east-1"`` or
            ``"gcp"`` for any GCP region.
        cpus: Minimum number of vCPUs (int) or a range string such as
            ``"4+"`` or ``"4-8"``. ``None`` lets SkyPilot decide.
        memory: Minimum RAM in GiB (int) or a range/suffix string such as
            ``"16+"`` or ``"16-32"``. ``None`` lets SkyPilot decide.
        accelerators: GPU/TPU specification, e.g. ``"A100:1"`` or
            ``"T4:4"``. ``None`` requests CPU-only resources.
        disk_size: Root disk size in GiB. ``None`` uses the cloud default.
        use_spot: If ``True``, request preemptible/spot instances to reduce
            cost. Defaults to ``False``.

    """

    infrastructure: str
    cpus: int | str | None = None
    memory: int | str | None = None
    accelerators: str | None = None
    disk_size: int | str | None = None
    use_spot: bool = False

    def to_sky_resources(self) -> Resources:
        """Convert to a SkyPilot :class:`sky.resources.Resources` object.

        Returns:
            A ``Resources`` instance populated from this config.

        """
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
    """Full specification of a SkyPilot managed job task.

    Attributes:
        name: Human-readable job name shown in the SkyPilot dashboard and logs.
        resources: Cloud resource requirements for the task.
        workdir: Local directory to sync to the remote cluster before running.
            ``None`` skips workdir upload.
        file_mounts: Cloud storage volumes to mount into the task container.
        env_vars: Environment variables injected at runtime (non-sensitive).
        secrets: Secret environment variables passed securely via SkyPilot's
            secrets mechanism and redacted from saved configs.
        setup_commands: Shell command(s) run once when the cluster is first
            provisioned (e.g. installing dependencies).
        run_commands: Shell command(s) that constitute the actual job workload.

    """

    name: str
    resources: ResourcesConfig
    workdir: Path | None = None
    file_mounts: list[FileMount] = field(default_factory=list)
    env_vars: dict[str, str] = field(default_factory=dict)
    secrets: dict[str, str] = field(default_factory=dict)
    setup_commands: str | list[str] | None = None
    run_commands: str | list[str] | None = None

    def to_sky_task(self) -> Task:
        """Convert to a SkyPilot :class:`sky.task.Task` object.

        Converts all nested config objects (resources, file mounts) to their
        SkyPilot SDK equivalents and assembles a ``Task`` ready to be passed
        to ``sky.jobs.launch``.

        Returns:
            A fully configured ``Task`` instance.

        """
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
