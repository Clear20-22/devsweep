# 🧹 devsweep

> **The Non-Destructive Developer Bloat & Storage Auditor.**  
> Find sizeable developer caches and storage candidates across your workstation (**macOS, Linux, Windows**) without modifying files during an audit.

---

## 🌟 Why devsweep?

Most system cleaners are either too generic or dangerously aggressive:
* They don't understand developer workflows (e.g. they don't know what `node_modules`, `.venv`, or `workspaceStorage` are).
* Or they delete everything indiscriminately, breaking virtual environments and logging you out of accounts.

**devsweep is different:**
* 🛡️ **Read-Only by Default**: It never deletes, renames, or touches your files while auditing. Cleanup is a separately generated, interactive, opt-in script.
* 🧠 **Developer-First Intelligence**:
  * Identifies **orphaned IDE workspaces** (VS Code, Cursor, Windsurf) that point to deleted repositories.
  * Correctly computes **sparse virtual disk allocations** (Docker `Docker.raw`, Colima, WSL2 `ext4.vhdx`) using actual allocated blocks instead of deceptive logical sizes.
  * Tracks multi-version toolchain caches across **Python** (`pip`, `uv`, `poetry`), **Node** (`npm`, `yarn`, `pnpm`, `node-gyp`), **Rust** (`cargo`, `rustup`), **Java** (`gradle`, `maven`), and **Go**.
  * Audits heavy **AI/ML weights** (`Hugging Face`, `PyTorch Hub`, `Ollama`).
* ⚡ **Zero-Dependency Ready**: Runs out-of-the-box using standard Python 3.8+, or enhances the experience with rich terminal UI tables if `rich` is installed.

---

## ⚡ Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-username/devsweep.git
cd devsweep

# 2. Run immediately (auto-configures environment on first run)
./ds
```

> [!TIP]
> You can also run `bash scripts/install.sh` if you prefer explicit setup first, or run `bash scripts/run.sh`.
> Run `./ds alias` to register `devsweep` and `ds` globally in your terminal shell so you can run them from any folder.

---

## 🖥️ Terminal Commands & Keywords

| Command / Keyword | What it does |
|---|---|
| `./ds` *(or `bash scripts/run.sh`)* | Opens the **interactive terminal menu** |
| `./ds help` | Shows instructions: **how to do, what to do, and commands** |
| `./ds scan` | Quick scan — global caches & toolchains only (1–2 sec) |
| `./ds full` | Full scan — includes project repositories |
| `./ds full ~/Work` | Full scan with a custom project root path |
| `./ds report` | Save an anonymised Markdown report → `audit-report.md` |
| `./ds report my.md` | Save Markdown report to a custom filename |
| `./ds json` | Save JSON report → `audit-report.json` |
| `./ds script` | Generate an interactive, commented cleanup script → `cleanup.sh` |
| `./ds clean` | Generate cleanup script **and** run it with step-by-step confirmation |
| `./ds alias` | Add `devsweep` and `ds` global commands to your shell (`~/.zshrc` / `~/.bashrc`) |

> [!NOTE]
> `./ds report` and `./ds json` automatically use `--redact` so usernames, home paths, and hostnames are safe to share.
> Cleanup scripts retain local paths so generated commands remain functional when you choose to execute them.

---

## 🎯 What devsweep Audits

| Module | What It Inspects | Safety Tier |
| :--- | :--- | :---: |
| **IDEs & Editors** | VS Code, Cursor, Windsurf orphaned `workspaceStorage` (checks if project directory still exists), cached `.vsix` installers, webview render caches, JetBrains caches, duplicate IDE app versions. | 🟢 Zero Risk / 🟡 Safe Cache |
| **Package Managers** | `pip`, `uv`, `poetry`, `npm`, `yarn`, `pnpm` global stores, `node-gyp` header caches, `cargo` registry caches, multi-version `gradle` jars, `maven` `.m2` repository, `go-build`, `Homebrew` bottles, and `APT`/`Pacman` caches. | 🟢 Zero Risk / 🟡 Safe Cache |
| **Language Runtimes** | Bun global install cache, Zig download & compilation cache, Deno remote modules & LSP cache, Flutter/Dart `.pub-cache` and toolchain artifacts. | 🟡 Safe Cache |
| **Data Science & Tools** | Conda/Mamba package tarballs and dormant environments, JupyterLab extension builds & runtime cache, Ruby/Gem store & Bundler cache, PHP Composer cache, Linux Snap cache and Flatpak runtimes. | 🟡 Safe Cache / 🔵 Review |
| **Containers & VMs** | Docker Desktop `Docker.raw` / WSL2 `.vhdx` sparse VM disks, Colima disks, Android Studio AVD emulator snapshots, Xcode `DerivedData` & `iOS DeviceSupport`, UTM virtual machines. | 🟡 Safe Cache / 🔵 Review |
| **AI & Machine Learning** | Hugging Face model hub cache, PyTorch Hub checkpoints, Ollama local LLM model weights, TensorFlow Hub modules. | 🟡 Safe Cache / 🔵 Review |
| **Project Repositories** | Scans workspaces (`~/Documents/GitHub`, `~/Projects`, etc.) for dormant `.venv`, bulky `node_modules`, `.next` build caches, Rust `target/`, and loose uncompacted `.git` objects. | 🟡 Safe Cache / 🔵 Review |
| **System & Browsers** | Arc, Safari, Chrome, Firefox, Brave HTTP asset caches, Telegram updater leftovers (`PersistentDownloads`), `.net/Updates` build dumps, system crash reports, and Trash. | 🟢 Zero Risk / 🟡 Safe Cache |

> [!NOTE]
> See [`report.example.md`](report.example.md) for a sample scan output with all paths anonymised.

---

## 📊 Safety Tiers Explained

All findings are categorized into 3 distinct safety tiers:

1. 🟢 **Zero Risk**:
   * Dead orphaned databases (pointing to deleted folders), leftover updater installers, temporary build dumps.
   * Usually safe to delete, but still verify the path and ensure the related app is closed.
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

# Create a report safe to share publicly:
# --redact hides your real hostname and replaces your home path (~) in output.
# NEVER commit report.json or report.md without --redact (see .gitignore).
python3 devsweep.py --redact --markdown shared-audit-report.md

# Generate an interactive, commented cleanup script that prompts before running each tier
python3 devsweep.py --generate-script cleanup.sh

# Windows: generate a PowerShell script, then run it from PowerShell
py devsweep.py --generate-script cleanup.ps1
.\cleanup.ps1

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

📖 **Full guide: [CONTRIBUTING.md](CONTRIBUTING.md)**

**Before submitting:**
- Every scanner module in `devsweep/modules/` should have a module-level docstring, section comments for each cache inspected, and a clear explanation of the safety tier chosen.
- Never commit personal scan output files (`report.json`, `report.md`). The `.gitignore` blocks these, but double-check with `git status` before pushing.
- See [`report.example.md`](report.example.md) for what a fully anonymised report looks like.

**Steps:**
1. Fork the repository
2. Create your feature branch (`git checkout -b feature/new-scanner`)
3. Commit your changes (`git commit -m 'Add scanner for Zig / Bun'`)
4. Push to the branch (`git push origin feature/new-scanner`)
5. Open a Pull Request

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for more information.
