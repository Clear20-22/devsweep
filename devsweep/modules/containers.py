"""
devsweep.modules.containers
============================

Scanner for container runtimes, virtual machines, and mobile device emulators.

What is inspected
-----------------
1. **Docker Desktop virtual disk** — The ``Docker.raw`` (macOS) or
   ``ext4.vhdx`` (Windows/WSL2) sparse image file that holds all container
   layers, volumes, and build cache.  We measure its *allocated* block size
   (not its logical maximum) via ``get_file_allocated_size``.

2. **Docker live reclaimable storage** — If the Docker daemon is running, we
   query ``docker system df`` to find dangling images and build cache that can
   be freed *without* wiping the VM disk.

3. **Colima** — A lightweight open-source alternative to Docker Desktop on
   macOS.  ``~/.colima`` holds its VM disk and configuration.

4. **Android Studio AVDs** — ``~/.android/avd`` contains emulator system
   snapshots.  ``~/Library/Android/sdk/system-images`` (macOS) or
   ``~/Android/Sdk/system-images`` (Linux/Windows) holds downloaded base OS
   images for different API levels.

5. **Xcode / iOS Simulator** *(macOS only)* — ``DerivedData`` holds Xcode
   build objects; ``iOS DeviceSupport`` holds debug symbols from physical
   devices; ``CoreSimulator/Caches`` holds simulator runtime caches.

6. **UTM Virtual Machines** *(macOS only)* — Full guest OS images managed by
   the UTM app.

Safety tiers
-------------
* SAFE_CACHE — Xcode DerivedData, device-support symbols, iOS simulator caches.
  These are auto-regenerated the next time you build or connect a device.
* REQUIRES_REVIEW — Docker VM disk, Colima, Android AVDs, Android SDK images,
  UTM VMs.  Deleting these would erase container state, running VMs, or
  emulator configurations that may be hard to reproduce.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import List

from devsweep.core.models import Category, Finding, SafetyLevel
from devsweep.core.scanner import BaseScanner
from devsweep.core.utils import (
    get_dir_size,
    get_home_dir,
    get_local_cache_dir,
    is_macos,
    is_windows,
)


class ContainerScanner(BaseScanner):
    """Scanner for Docker, Colima, Android emulators, Xcode, and UTM."""

    @property
    def name(self) -> str:
        return "virtualization"

    @property
    def description(self) -> str:
        return (
            "Scans Docker VM disks, Colima, Android AVDs, "
            "Xcode DerivedData, and simulator caches"
        )

    def scan(self) -> List[Finding]:
        findings: List[Finding] = []
        home = get_home_dir()
        local_app_data = get_local_cache_dir()

        # ------------------------------------------------------------------
        # 1. Docker Desktop virtual disk
        #
        #    macOS path: ~/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw
        #    Windows path: %LOCALAPPDATA%/Docker/wsl/data/ext4.vhdx
        #
        #    These are sparse files — the logical size shown in Finder/Explorer
        #    is the *maximum* the disk can grow to, but the actual on-disk
        #    footprint can be much smaller.  ``get_dir_size`` uses ``st_blocks``
        #    to measure the true allocation.
        #
        #    We break after the first match because Docker only creates one VM
        #    disk per installation.
        # ------------------------------------------------------------------
        docker_vm_paths = [
            # macOS: Docker Desktop for Mac
            home / "Library" / "Containers" / "com.docker.docker" / "Data" / "vms" / "0" / "data" / "Docker.raw",
            # Windows: Docker with WSL2 backend
            local_app_data / "Docker" / "wsl" / "data" / "ext4.vhdx",
        ]
        for vm_disk in docker_vm_paths:
            if vm_disk.exists():
                sz = get_dir_size(vm_disk)
                if sz > 1024 * 1024 * 1024:  # report only when > 1 GB
                    findings.append(Finding(
                        id="docker_desktop_vm_disk",
                        title="Docker Desktop Virtual Disk (Docker.raw / vhdx)",
                        category=Category.VIRTUALIZATION,
                        safety=SafetyLevel.REQUIRES_REVIEW,
                        path=str(vm_disk),
                        size_bytes=sz,
                        description=(
                            "Virtual disk holding Docker container layers, volumes, and images. "
                            "Running `docker system prune` reclaims space inside the disk but "
                            "does not shrink the file itself — see Docker's disk reclaim docs."
                        ),
                        cleanup_command=(
                            "docker system prune -a --volumes  "
                            "# Run inside Docker Desktop or CLI"
                        ),
                    ))
                break  # Only one VM disk exists per Docker Desktop installation.

        # ------------------------------------------------------------------
        # 1b. Docker live reclaimable storage (requires daemon to be running)
        #
        #     ``docker system df`` reports dangling images, stopped containers,
        #     and build cache.  Unlike the VM-disk finding above, `docker system
        #     prune` actually frees this space immediately without any risk of
        #     data loss (only unused resources are pruned).
        #
        #     Timeout is set low (3 s) so a non-responsive daemon does not
        #     block the scan.
        # ------------------------------------------------------------------
        if shutil.which("docker"):
            try:
                res = subprocess.run(
                    ["docker", "system", "df", "--format", "{{json .}}"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if res.returncode == 0 and res.stdout.strip():
                    reclaimable_sum = 0
                    # Each line is a separate JSON object (one per resource type).
                    for line in res.stdout.strip().splitlines():
                        try:
                            item = json.loads(line)
                            reclaim_str = item.get("Reclaimable", "")
                            # Parse human-readable sizes like "1.2GB (50%)" or "350MB"
                            if "GB" in reclaim_str:
                                reclaimable_sum += int(
                                    float(reclaim_str.split("GB")[0].strip()) * 1024**3
                                )
                            elif "MB" in reclaim_str:
                                reclaimable_sum += int(
                                    float(reclaim_str.split("MB")[0].strip()) * 1024**2
                                )
                        except Exception:
                            pass  # Ignore malformed lines from unexpected Docker output.

                    if reclaimable_sum > 500 * 1024 * 1024:  # > 500 MB
                        findings.append(Finding(
                            id="docker_live_reclaimable",
                            title="Docker Reclaimable Images & Build Cache",
                            category=Category.VIRTUALIZATION,
                            safety=SafetyLevel.SAFE_CACHE,
                            path="docker daemon",
                            size_bytes=reclaimable_sum,
                            description=(
                                "Unused container images and build cache identified by "
                                "`docker system df`.  These are safe to remove — only "
                                "images and cache not referenced by a running container are pruned."
                            ),
                            cleanup_command="docker system prune -f",
                        ))
            except Exception:
                pass  # Docker daemon is not running or docker binary is not accessible.

        # ------------------------------------------------------------------
        # 2. Colima VM storage
        #    ~/.colima
        #
        #    Colima is a CLI-based Docker/containerd runtime for macOS that
        #    uses Lima (a QEMU-based Linux VM) under the hood.  The ``~/.colima``
        #    directory contains the VM disk image and its configuration.
        #    Deleting it removes the entire Colima instance — use REQUIRES_REVIEW.
        # ------------------------------------------------------------------
        colima_dir = home / ".colima"
        if colima_dir.exists():
            sz = get_dir_size(colima_dir)
            if sz > 500 * 1024 * 1024:
                findings.append(Finding(
                    id="colima_vm_storage",
                    title="Colima Container Runtime Disk & Cache",
                    category=Category.VIRTUALIZATION,
                    safety=SafetyLevel.REQUIRES_REVIEW,
                    path=str(colima_dir),
                    size_bytes=sz,
                    description=(
                        "Colima virtual machine disk image and downloaded container layers."
                    ),
                    cleanup_command="colima delete  # or: colima prune",
                ))

        # ------------------------------------------------------------------
        # 3a. Android Studio AVD emulator snapshots
        #     ~/.android/avd
        #
        #     Each AVD entry is a directory containing a full system snapshot
        #     of the emulated Android device.  These can be many GB per device.
        #     Unused AVDs should be deleted from the AVD Manager in Android Studio.
        # ------------------------------------------------------------------
        avd_dir = home / ".android" / "avd"
        if avd_dir.exists():
            sz = get_dir_size(avd_dir)
            if sz > 500 * 1024 * 1024:
                findings.append(Finding(
                    id="android_avd_images",
                    title="Android Virtual Device (AVD) Emulators",
                    category=Category.VIRTUALIZATION,
                    safety=SafetyLevel.REQUIRES_REVIEW,
                    path=str(avd_dir),
                    size_bytes=sz,
                    description=(
                        "Emulated Android system disks and snapshots. "
                        "Remove unused devices from AVD Manager inside Android Studio."
                    ),
                    cleanup_command="rm -rf ~/.android/avd/<unused-avd>.avd",
                ))

        # ------------------------------------------------------------------
        # 3b. Android SDK system images
        #
        #    Android Studio downloads OS images for each API level / ABI combo.
        #    Platform-specific search order mirrors the default SDK install locations.
        # ------------------------------------------------------------------
        android_system_images = [
            home / "Library" / "Android" / "sdk" / "system-images",   # macOS
            home / "Android" / "Sdk" / "system-images",                # Linux
            local_app_data / "Android" / "Sdk" / "system-images",     # Windows
        ]
        for img_path in android_system_images:
            if img_path.exists():
                sz = get_dir_size(img_path)
                if sz > 1024 * 1024 * 1024:  # > 1 GB
                    findings.append(Finding(
                        id="android_sdk_system_images",
                        title="Android SDK Downloaded System Images",
                        category=Category.VIRTUALIZATION,
                        safety=SafetyLevel.REQUIRES_REVIEW,
                        path=str(img_path),
                        size_bytes=sz,
                        description=(
                            "Base Android OS emulator images for various API levels. "
                            "Unused API levels can be removed via the SDK Manager in Android Studio."
                        ),
                        cleanup_command=(
                            "# Use Android Studio SDK Manager to remove unused system images"
                        ),
                    ))
                break  # Only the first matching SDK path is reported.

        # ------------------------------------------------------------------
        # 4. Xcode and iOS Simulator caches (macOS only)
        # ------------------------------------------------------------------
        if is_macos():
            # 4a. Xcode DerivedData
            #     ~/Library/Developer/Xcode/DerivedData
            #
            #     Contains compiled object files, module caches, and search
            #     indices for every Xcode project ever opened.  Fully
            #     auto-regenerated the next time Xcode builds the project.
            xcode_derived = home / "Library" / "Developer" / "Xcode" / "DerivedData"
            if xcode_derived.exists():
                sz = get_dir_size(xcode_derived)
                if sz > 500 * 1024 * 1024:
                    findings.append(Finding(
                        id="xcode_derived_data",
                        title="Xcode DerivedData Build Artifacts",
                        category=Category.VIRTUALIZATION,
                        safety=SafetyLevel.SAFE_CACHE,
                        path=str(xcode_derived),
                        size_bytes=sz,
                        description=(
                            "Xcode intermediate build objects, module caches, and index files. "
                            "Safely removed — Xcode will rebuild on next project open."
                        ),
                        cleanup_command=f'rm -rf "{xcode_derived}"/*',
                    ))

            # 4b. iOS DeviceSupport debug symbols
            #     ~/Library/Developer/Xcode/iOS DeviceSupport
            #
            #     Xcode copies debug symbols from physical iOS devices connected
            #     via USB.  Each device × OS version combination adds a folder
            #     here.  Old entries from devices you no longer own are safe to
            #     remove — Xcode will re-copy them if you reconnect the device.
            xcode_device_support = home / "Library" / "Developer" / "Xcode" / "iOS DeviceSupport"
            if xcode_device_support.exists():
                sz = get_dir_size(xcode_device_support)
                if sz > 500 * 1024 * 1024:
                    findings.append(Finding(
                        id="xcode_device_support",
                        title="Xcode iOS DeviceSupport Debug Symbols",
                        category=Category.VIRTUALIZATION,
                        safety=SafetyLevel.SAFE_CACHE,
                        path=str(xcode_device_support),
                        size_bytes=sz,
                        description=(
                            "Symbols from previously connected physical iOS devices. "
                            "Entries for old iOS versions or devices you no longer use are safe to remove."
                        ),
                        cleanup_command=f'rm -rf "{xcode_device_support}"/*',
                    ))

            # 4c. iOS CoreSimulator caches
            #     ~/Library/Developer/CoreSimulator/Caches
            #
            #     Temporary runtime caches generated when iOS simulators are
            #     launched.  They are rebuilt automatically.
            simulator_caches = home / "Library" / "Developer" / "CoreSimulator" / "Caches"
            if simulator_caches.exists():
                sz = get_dir_size(simulator_caches)
                if sz > 200 * 1024 * 1024:
                    findings.append(Finding(
                        id="core_simulator_caches",
                        title="iOS CoreSimulator Temporary Caches",
                        category=Category.VIRTUALIZATION,
                        safety=SafetyLevel.SAFE_CACHE,
                        path=str(simulator_caches),
                        size_bytes=sz,
                        description=(
                            "Runtime caches for iOS simulators. "
                            "Rebuilt automatically when simulators are launched."
                        ),
                        cleanup_command=(
                            "xcrun simctl erase all  "
                            "# or manually: rm -rf CoreSimulator/Caches/*"
                        ),
                    ))

        # ------------------------------------------------------------------
        # 5. UTM Virtual Machines (macOS only)
        #    ~/Library/Containers/com.utmapp.UTM/Data/Documents
        #
        #    UTM is a popular free virtualisation front-end for macOS (based
        #    on QEMU / Apple Hypervisor).  Each VM is a bundle stored here.
        #    We mark these REQUIRES_REVIEW — UTM VMs may contain live data.
        # ------------------------------------------------------------------
        if is_macos():
            utm_dir = (
                home / "Library" / "Containers" / "com.utmapp.UTM" / "Data" / "Documents"
            )
            if utm_dir.exists():
                sz = get_dir_size(utm_dir)
                if sz > 500 * 1024 * 1024:
                    findings.append(Finding(
                        id="utm_virtual_machines",
                        title="UTM Virtual Machine Disk Images",
                        category=Category.VIRTUALIZATION,
                        safety=SafetyLevel.REQUIRES_REVIEW,
                        path=str(utm_dir),
                        size_bytes=sz,
                        description=(
                            "Guest OS images configured inside UTM. "
                            "Delete unused VMs directly from the UTM application."
                        ),
                        cleanup_command=(
                            "# Delete unused VMs directly inside UTM application"
                        ),
                    ))

        return findings
