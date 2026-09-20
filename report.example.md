# 🧹 devsweep Storage & Developer Bloat Audit Report

> **This is an example report.**  Generate your own by running:
> ```bash
> python3 devsweep.py --redact --markdown my-report.md
> ```
> The `--redact` flag replaces your hostname and home path with safe placeholders.

---

- **Operating System**: macOS-15.x-arm64-arm-64bit-Mach-O
- **Hostname**: `<redacted>`
- **Free Disk Space**: 85.00 GB (out of 228.27 GB)
- **Total Reclaimable Space**: **29.00 GB**
- **Scan Time**: 6.02 seconds

## 📊 Space Savings Breakdown

| Tier | Reclaimable Space | Impact & Description |
| :--- | :---: | :--- |
| 🟢 **Low Risk** | **0 B** | Dead orphans, installer packages, update dumps. Verify paths first. |
| 🟡 **Safe Caches** | **13.00 GB** | Dev toolchain, compiler, and browser caches. Auto-rebuilds on demand. |
| 🔵 **Requires Review** | **16.00 GB** | Project virtualenvs, Docker VMs, or duplicate app installations. |

## 🔍 Detailed Findings

| Category | Component / Target | Size | Safety | Details |
| :--- | :--- | :---: | :---: | :--- |
| Containers, VMs & Emulators | `Docker Desktop Virtual Disk (Docker.raw / vhdx)` | **5.18 GB** | 🔵 Review | Virtual disk holding Docker container layers, volumes, and images. |
| Containers, VMs & Emulators | `Colima Container Runtime Disk & Cache` | **3.65 GB** | 🔵 Review | Colima virtual machine disk image and downloaded container layers. |
| System Caches & Browsers | `Arc Browser Service Worker Offline Cache` | **3.56 GB** | 🟡 Safe Cache | Offline website service worker scripts cached by Arc Browser. |
| Project Artifacts & Repositories | `Python Virtualenv in 'my-ml-project'` | **3.48 GB** | 🔵 Review | Virtual environment inside my-ml-project. Can be re-created via `uv venv` or `python -m venv` if dependencies are specified in requirements.txt or pyproject.toml. |
| System Caches & Browsers | `Safari WebKit & HTTP Disk Cache` | **3.28 GB** | 🟡 Safe Cache | Safari temporary website asset and render caches. |
| Package Managers & Toolchains | `Gradle Multi-Version Dependency Cache` | **2.82 GB** | 🟡 Safe Cache | Jar files, transforms, and metadata cached across past Gradle builds. |
| System Caches & Browsers | `Arc Browser Cache` | **1.99 GB** | 🟡 Safe Cache | Temporary HTTP asset and media cache. Safely rebuilds as you browse. |
| Project Artifacts & Repositories | `Python Virtualenv in 'my-thesis-project'` | **1.48 GB** | 🔵 Review | Virtual environment inside my-thesis-project. Can be re-created via `uv venv` or `python -m venv` if dependencies are specified in requirements.txt or pyproject.toml. |
| Project Artifacts & Repositories | `Large Git Objects Database in 'my-big-repo'` | **1.37 GB** | 🟡 Safe Cache | Git object repository in my-big-repo contains uncompressed/loose objects. Repacking with `git gc --prune=now` will compress and deduplicate history. |
| IDEs & Editors | `VS Code Orphaned Workspaces (12 folders)` | **1.23 GB** | 🟢 Zero Risk | 12 workspace database entries reference project directories that no longer exist on your filesystem. |
| Project Artifacts & Repositories | `node_modules in 'my-web-app'` | **719.7 MB** | 🔵 Review | Installed Node dependencies for my-web-app. Re-installable with `npm install` / `pnpm install`. |
| Project Artifacts & Repositories | `Python Virtualenv in 'my-api-project'` | **400.0 MB** | 🔵 Review | Virtual environment inside my-api-project. Can be re-created via `uv venv` or `python -m venv`. |
| Package Managers & Toolchains | `Homebrew Package Download Cache` | **113.4 MB** | 🟡 Safe Cache | Downloaded bottles and git clones from brew install. |

## 🛠️ Recommended Cleanup Commands

### 🟢 Tier 1: Zero Risk Instant Cleanup
```bash
# No zero-risk runnable commands in this example.
# VS Code orphaned workspaces: run `devsweep --generate-script cleanup.sh`
```

### 🟡 Tier 2: Safe Cache Purge (Rebuilds automatically as needed)
```bash
rm -rf "~/Library/Application Support/Arc/User Data/Default/Service Worker"/*
rm -rf "~/.gradle/caches"/*
rm -rf "~/Library/Caches/Arc"/*
cd "~/repos/my-big-repo" && git gc --prune=now --aggressive
brew cleanup -s --prune=all
```

---
*Generated automatically by [devsweep](https://github.com/your-username/devsweep) — Non-destructive developer bloat auditor.*
