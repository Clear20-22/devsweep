# 🧹 devsweep

> **The Non-Destructive Developer Bloat & Storage Auditor.**  
> Find every gigabyte of hidden developer bloat across your workstation (**macOS, Linux, Windows**) with **0% risk of data loss**.

---

## 🌟 Why devsweep?

Most system cleaners are either too generic or dangerously aggressive:
* They don't understand developer workflows (e.g. they don't know what `node_modules`, `.venv`, or `workspaceStorage` are).
* Or they delete everything indiscriminately, breaking virtual environments and logging you out of accounts.

**devsweep is different:**
* 🛡️ **100% Read-Only & Non-Destructive**: It never deletes, renames, or touches your files. It only audits, measures, and outputs clear, actionable recommendations.
* 🧠 **Developer-First Intelligence**:
  * Identifies **orphaned IDE workspaces** (VS Code, Cursor, Windsurf) that point to deleted repositories.
  * Correctly computes **sparse virtual disk allocations** (Docker `Docker.raw`, Colima, WSL2 `ext4.vhdx`) using actual allocated blocks instead of deceptive logical sizes.
  * Tracks multi-version toolchain caches across **Python** (`pip`, `uv`, `poetry`), **Node** (`npm`, `yarn`, `pnpm`, `node-gyp`), **Rust** (`cargo`, `rustup`), **Java** (`gradle`, `maven`), and **Go**.
  * Audits heavy **AI/ML weights** (`Hugging Face`, `PyTorch Hub`, `Ollama`).
* ⚡ **Zero-Dependency Ready**: Runs out-of-the-box using standard Python 3.8+, or enhances the experience with rich terminal UI tables if `rich` is installed.

---

## 🚀 Quick Start

### 1. Instant Run (No Installation Required)

Clone and run with standard Python 3:

```bash
git clone https://github.com/jubayerahmedsojib/devsweep.git
cd devsweep
python3 devsweep.py
```

### 2. Enhanced Terminal Experience (with Rich UI)

Using `uv` (recommended):

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
python devsweep.py
```

Or using standard `pip`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python devsweep.py
```

---

## 🎯 What devsweep Audits

| Module | What It Inspects | Safety Tier |
| :--- | :--- | :---: |
| **IDEs & Editors** | VS Code, Cursor, Windsurf orphaned `workspaceStorage` (checks if project directory still exists), cached `.vsix` installers, webview render caches, JetBrains caches, duplicate IDE app versions. | 🟢 Zero Risk / 🟡 Safe Cache |
| **Package Managers** | `pip`, `uv`, `poetry`, `npm`, `yarn`, `pnpm` global stores, `node-gyp` header caches, `cargo` registry caches, multi-version `gradle` jars, `maven` `.m2` repository, `go-build`, `Homebrew` bottles, and `APT`/`Pacman` caches. | 🟢 Zero Risk / 🟡 Safe Cache |
| **Containers & VMs** | Docker Desktop `Docker.raw` / WSL2 `.vhdx` sparse VM disks, Colima disks, Android Studio AVD emulator snapshots, Xcode `DerivedData` & `iOS DeviceSupport`, UTM virtual machines. | 🟡 Safe Cache / 🔵 Review |
| **AI & Machine Learning** | Hugging Face model hub cache, PyTorch Hub checkpoints, Ollama local LLM model weights, TensorFlow Hub modules. | 🟡 Safe Cache / 🔵 Review |
| **Project Repositories** | Scans workspaces (`~/Documents/GitHub`, `~/Projects`, etc.) for dormant `.venv`, bulky `node_modules`, `.next` build caches, Rust `target/`, and loose uncompacted `.git` objects. | 🟡 Safe Cache / 🔵 Review |
| **System & Browsers** | Arc, Safari, Chrome, Firefox, Brave HTTP asset caches, Telegram updater leftovers (`PersistentDownloads`), `.net/Updates` build dumps, system crash reports, and Trash. | 🟢 Zero Risk / 🟡 Safe Cache |

---

## 📊 Safety Tiers Explained

All findings are categorized into 3 distinct safety tiers:

1. 🟢 **Zero Risk**:
   * Dead orphaned databases (pointing to deleted folders), leftover updater installers, temporary build dumps.
   * **100% safe to delete immediately.**
2. 🟡 **Safe Caches**:
   * Dev toolchain download caches, build artifacts, browser HTTP asset caches.
   * **Safe to clear.** Any cache will rebuild or redownload automatically if a script or project requests it in the future.
3. 🔵 **Requires Review**:
   * Project virtual environments, Docker VM images, active `node_modules`, and duplicate application installations.
   * Highlighted so you can review before deciding whether to purge.

---

## 🛠️ CLI Flags & Options

```bash
# Export audit results to Markdown (great for sharing or saving)
python3 devsweep.py --markdown audit-report.md

# Export audit results to machine-readable JSON
python3 devsweep.py --json audit-report.json

# Generate an interactive, commented cleanup script that prompts before running each tier
python3 devsweep.py --generate-script cleanup.sh

# Scan specific custom project directories
python3 devsweep.py --scan-projects ~/Work ~/Personal/Apps

# Skip scanning local project repositories (focus only on global toolchains & system caches)
python3 devsweep.py --skip-projects

# Run silently without printing recommended commands
python3 devsweep.py --no-commands
```

---

## 💻 Cross-Platform Support

* 🍏 **macOS**: Full native support for Apple Silicon (arm64) and Intel (x86_64), macOS Containers, Xcode, Homebrew, and Safari.
* 🐧 **Linux**: Ubuntu, Debian, Fedora, Arch Linux (APT, Pacman, Snap, Flatpak, Docker, system caches).
* 🪟 **Windows**: Windows 10 & 11 (AppData, LocalAppData, Docker WSL2 vhdx, pip, npm, winget, VS Code).

---

## 🤝 Contributing

Contributions are welcome! If there is a new developer tool, language cache, or framework you would like `devsweep` to audit, feel free to submit a PR or open an issue.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/new-scanner`)
3. Commit your changes (`git commit -m 'Add scanner for Zig / Bun'`)
4. Push to the branch (`git push origin feature/new-scanner`)
5. Open a Pull Request

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for more information.
