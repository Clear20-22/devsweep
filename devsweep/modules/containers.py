"""Containers, Virtual Machines, and Emulators bloat scanner."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import List

from devsweep.core.models import Category, Finding, SafetyLevel
from devsweep.core.scanner import BaseScanner
from devsweep.core.utils import get_dir_size, get_home_dir, get_local_cache_dir, is_macos, is_windows


class ContainerScanner(BaseScanner):
    @property
    def name(self) -> str:
        return "virtualization"

    @property
    def description(self) -> str:
        return "Scans Docker VM disks, Colima, Android AVDs, Xcode DerivedData, and simulator caches"

    def scan(self) -> List[Finding]:
        findings: List[Finding] = []
        home = get_home_dir()
        local_app_data = get_local_cache_dir()

        # -------------------------------------------------------------
        # 1. Docker Desktop Virtual Disk & System Data
        # -------------------------------------------------------------
        docker_vm_paths = [
            home / "Library" / "Containers" / "com.docker.docker" / "Data" / "vms" / "0" / "data" / "Docker.raw",
            local_app_data / "Docker" / "wsl" / "data" / "ext4.vhdx",
        ]
        for vm_disk in docker_vm_paths:
            if vm_disk.exists():
                sz = get_dir_size(vm_disk)
                if sz > 1024 * 1024 * 1024:  # > 1GB
                    findings.append(Finding(
                        id="docker_desktop_vm_disk",
                        title="Docker Desktop Virtual Disk (Docker.raw / vhdx)",
                        category=Category.VIRTUALIZATION,
                        safety=SafetyLevel.REQUIRES_REVIEW,
                        path=str(vm_disk),
                        size_bytes=sz,
                        description="Virtual disk holding Docker container layers, volumes, and images.",
                        cleanup_command="docker system prune -a --volumes  # Run inside Docker Desktop or CLI"
                    ))
                break

        # If docker CLI is responsive, query live docker storage
        if shutil.which("docker"):
            try:
                res = subprocess.run(
                    ["docker", "system", "df", "--format", "{{json .}}"],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if res.returncode == 0 and res.stdout.strip():
                    reclaimable_sum = 0
                    for line in res.stdout.strip().splitlines():
                        try:
                            item = json.loads(line)
                            reclaim_str = item.get("Reclaimable", "")
                            # Parse reclaim string if present
                            if "GB" in reclaim_str:
                                reclaimable_sum += int(float(reclaim_str.split("GB")[0].strip()) * 1024**3)
                            elif "MB" in reclaim_str:
                                reclaimable_sum += int(float(reclaim_str.split("MB")[0].strip()) * 1024**2)
                        except Exception:
                            pass

                    if reclaimable_sum > 500 * 1024 * 1024:
                        findings.append(Finding(
                            id="docker_live_reclaimable",
                            title="Docker Reclaimable Images & Build Cache",
                            category=Category.VIRTUALIZATION,
                            safety=SafetyLevel.SAFE_CACHE,
                            path="docker daemon",
                            size_bytes=reclaimable_sum,
                            description="Unused container images and build cache identified by docker system df.",
                            cleanup_command="docker system prune -f"
                        ))
            except Exception:
                pass

        # -------------------------------------------------------------
        # 2. Colima VM
        # -------------------------------------------------------------
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
                    description="Colima virtual machine disk image and downloaded container layers.",
                    cleanup_command="colima delete  # or colima prune"
                ))

        # -------------------------------------------------------------
        # 3. Android Studio & Emulator AVD Images
        # -------------------------------------------------------------
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
                    description="Emulated Android system disks and snapshots. Remove unused devices from AVD Manager.",
                    cleanup_command="rm -rf ~/.android/avd/<unused-avd>.avd"
                ))

        android_system_images = [
            home / "Library" / "Android" / "sdk" / "system-images",
            home / "Android" / "Sdk" / "system-images",
            local_app_data / "Android" / "Sdk" / "system-images",
        ]
        for img_path in android_system_images:
            if img_path.exists():
                sz = get_dir_size(img_path)
                if sz > 1024 * 1024 * 1024:
                    findings.append(Finding(
                        id="android_sdk_system_images",
                        title="Android SDK Downloaded System Images",
                        category=Category.VIRTUALIZATION,
                        safety=SafetyLevel.REQUIRES_REVIEW,
                        path=str(img_path),
                        size_bytes=sz,
                        description="Base Android OS emulator images for various API levels.",
                        cleanup_command=f"# Use Android Studio SDK Manager or delete unused system-images"
                    ))
                break

        # -------------------------------------------------------------
        # 4. Xcode & iOS Simulator Caches (macOS)
        # -------------------------------------------------------------
        if is_macos():
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
                        description="Xcode intermediate build objects, module caches, and index files.",
                        cleanup_command=f'rm -rf "{xcode_derived}"/*'
                    ))

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
                        description="Symbols from previously connected physical iOS devices.",
                        cleanup_command=f'rm -rf "{xcode_device_support}"/*'
                    ))

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
                        description="Runtime caches for iOS simulators.",
                        cleanup_command="xcrun simctl erase all  # or rm -rf simulator caches"
                    ))

        # -------------------------------------------------------------
        # 5. UTM Virtual Machines (macOS)
        # -------------------------------------------------------------
        if is_macos():
            utm_dir = home / "Library" / "Containers" / "com.utmapp.UTM" / "Data" / "Documents"
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
                        description="Guest OS images configured inside UTM.",
                        cleanup_command="# Delete unused VMs directly inside UTM application"
                    ))

        return findings
