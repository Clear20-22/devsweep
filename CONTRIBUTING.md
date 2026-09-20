# 🤝 Contributing to devsweep

Thank you for your interest in contributing! devsweep is designed to be **easy to extend** — adding a new scanner, reporter, or category takes only a few minutes if you follow this guide.

---

## 📋 Table of Contents

1. [Project Structure](#-project-structure)
2. [How to Add a New Scanner Module](#-how-to-add-a-new-scanner-module)
3. [How to Add a New Category](#-how-to-add-a-new-category)
4. [How to Add a New Reporter](#-how-to-add-a-new-reporter)
5. [Code Style & Comment Requirements](#-code-style--comment-requirements)
6. [Testing](#-testing)
7. [Pull Request Checklist](#-pull-request-checklist)

---

## 📁 Project Structure

```
devsweep/
├── devsweep.py              ← standalone entry point (python3 devsweep.py)
├── devsweep/
│   ├── __init__.py
│   ├── cli.py               ← argument parser + scanner orchestration
│   ├── core/
│   │   ├── models.py        ← Finding, ScanReport, SafetyLevel, Category
│   │   ├── scanner.py       ← BaseScanner abstract class
│   │   └── utils.py         ← cross-platform helpers (paths, sizes, redact)
│   ├── modules/             ← ⭐ ADD NEW SCANNERS HERE
│   │   ├── ai_ml.py
│   │   ├── containers.py
│   │   ├── ides.py
│   │   ├── package_managers.py
│   │   ├── projects.py
│   │   └── system_browsers.py
│   └── reporters/           ← terminal, JSON, Markdown, script output
│       ├── json_rep.py
│       ├── markdown_rep.py
│       ├── script_gen.py
│       └── terminal.py
└── tests/
    └── test_reporters.py
```

---

## ⭐ How to Add a New Scanner Module

### Step 1 — Create your module file

Create a new file in `devsweep/modules/`, e.g. `devsweep/modules/my_tool.py`.

Use the template below as your starting point:

```python
"""
devsweep.modules.my_tool
=========================

Scanner for <brief description of what this scans>.

What is inspected
-----------------
* **Cache name** (``~/.cache/my_tool``) — brief description.
* **Another cache** (``~/.my_tool/data``) — brief description.

Safety tiers
-------------
* SAFE_CACHE — caches that rebuild automatically on next use.
* REQUIRES_REVIEW — data the user may still need (e.g. downloaded models, VMs).
"""

from pathlib import Path
from typing import List

from devsweep.core.models import Category, Finding, SafetyLevel
from devsweep.core.scanner import BaseScanner
from devsweep.core.utils import get_dir_size, get_home_dir, is_macos, is_windows


class MyToolScanner(BaseScanner):
    """Scanner for <your tool name> caches and artefacts."""

    @property
    def name(self) -> str:
        # Short snake_case ID — shown in error messages.
        return "my_tool"

    @property
    def description(self) -> str:
        return "Scans ~/.my_tool cache for stale downloads and build artefacts"

    def scan(self) -> List[Finding]:
        findings: List[Finding] = []
        home = get_home_dir()

        # ------------------------------------------------------------------
        # 1. My tool download cache
        #    ~/.cache/my_tool  (Linux/macOS)
        #
        #    Brief explanation of what is stored here and why it is safe to
        #    delete (or why it needs review).
        # ------------------------------------------------------------------
        cache = home / ".cache" / "my_tool"
        if cache.exists():
            sz = get_dir_size(cache)
            if sz > 50 * 1024 * 1024:          # Only report when > 50 MB
                findings.append(Finding(
                    id="my_tool_cache",
                    title="MyTool Download Cache",
                    category=Category.PACKAGE_MANAGERS,  # pick the best fit
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(cache),
                    size_bytes=sz,
                    description=(
                        "Cached packages from MyTool installs. "
                        "Re-populated automatically on next use."
                    ),
                    cleanup_command="my_tool cache purge",
                ))

        # Add more cache locations following the same pattern...

        return findings
```

### Step 2 — Register your scanner in `cli.py`

Open [`devsweep/cli.py`](devsweep/cli.py) and add two lines:

```python
# At the top — import your new scanner
from devsweep.modules.my_tool import MyToolScanner

# In main() — add to the scanners list
scanners = [
    IDEScanner(),
    PackageManagerScanner(),
    ContainerScanner(),
    AIMLScanner(),
    SystemBrowserScanner(),
    MyToolScanner(),          # ← add here
]
```

### Step 3 — Test it

```bash
python3 devsweep.py
```

Your new findings should appear in the terminal table under the category you chose.

---

## 🏷️ How to Add a New Category

If your scanner doesn't fit any existing category, add one in [`devsweep/core/models.py`](devsweep/core/models.py):

```python
class Category(str, Enum):
    PACKAGE_MANAGERS = "Package Managers & Toolchains"
    IDES_EDITORS     = "IDEs & Editors"
    VIRTUALIZATION   = "Containers, VMs & Emulators"
    AI_ML            = "AI & Machine Learning"
    PROJECTS         = "Project Artifacts & Repositories"
    SYSTEM_BROWSERS  = "System Caches & Browsers"
    MY_NEW_CATEGORY  = "My New Category"   # ← add here
```

The string value is used verbatim in the terminal table, JSON, and Markdown reports.

---

## 📊 How to Add a New Reporter

Reporters live in `devsweep/reporters/`. Each one receives a `ScanReport` object and writes output somewhere (file, stdout, etc.).

```python
# devsweep/reporters/my_reporter.py
from pathlib import Path
from devsweep.core.models import ScanReport

def generate_my_report(report: ScanReport, output_path: Path) -> None:
    """Write report in my custom format."""
    ...
```

Then wire it up in `cli.py` with a new `--my-format` argument following the same pattern as `--json` and `--markdown`.

---

## ✍️ Code Style & Comment Requirements

Every contribution **must** include:

| Requirement | Example |
|---|---|
| **Module docstring** | `What is inspected`, `Safety tiers` sections |
| **Class docstring** | One-sentence summary of what the scanner covers |
| **Method docstrings** | Parameters, return value, what it does |
| **Section comments** | One block comment per cache/tool explaining *why* the safety tier was chosen |
| **Size threshold comment** | `# only report when > 50 MB` |

### Choosing the right `SafetyLevel`

| Use | When |
|---|---|
| `ZERO_RISK` | The file is **completely orphaned** — no app references it. Dead installer DMGs, workspace entries pointing to deleted folders. |
| `SAFE_CACHE` | The tool will **auto-regenerate** the cache on next use. Build outputs, download caches, render caches. |
| `REQUIRES_REVIEW` | The user may **still need this**. Virtualenvs, VM disk images, locally pulled AI models. |

---

## 🧪 Testing

Run the test suite before opening a PR:

```bash
# Install test dependencies
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v
```

For new scanners, add tests in `tests/` that verify:
- The scanner returns an empty list when the target directory doesn't exist.
- The scanner correctly identifies and sizes a mock cache directory.
- Any custom helper functions behave correctly at edge cases.

---

## ✅ Pull Request Checklist

Before submitting your PR, make sure:

- [ ] New scanner file has a **module docstring** with `What is inspected` and `Safety tiers` sections
- [ ] Every cache block has a **section comment** explaining what is stored and why the safety tier was chosen
- [ ] Scanner is added to the `scanners` list in `cli.py`
- [ ] All **existing tests pass**: `python -m pytest tests/ -v`
- [ ] You have **not committed** any `report.json`, `report.md`, `cleanup.sh`, or `cleanup.ps1` files (run `git status` to check)
- [ ] PR title follows: `feat: Add scanner for <Tool Name>`
- [ ] PR description explains: what the scanner detects, which OS(es) it supports, and which safety tier each finding uses

---

## 💡 Ideas for New Scanners

Looking for something to build? Here are some ideas the community would love:

| Scanner Idea | What to scan |
|---|---|
| **Bun** | `~/.bun/install/cache` |
| **Zig** | `~/.cache/zig` |
| **Deno** | `~/.cache/deno` |
| **Flutter/Dart** | `~/.pub-cache`, `~/.dart_tool` |
| **Ruby/Gem** | `~/.gem`, `~/.bundle/cache` |
| **Swift/CocoaPods** | `~/.cocoapods`, `~/Library/Developer/Xcode/DerivedData` |
| **Snap packages** | `/var/lib/snapd/cache` |
| **Flatpak** | `~/.local/share/flatpak` |
| **JupyterLab** | `~/.local/share/jupyter` |
| **Conda/Mamba** | `~/miniconda3/pkgs`, `~/anaconda3/pkgs` |
| **PHP/Composer** | `~/.composer/cache` |
| **Ruby on Rails** | `tmp/cache`, `log/*.log` in project dirs |

---

*Questions? Open a [GitHub Issue](https://github.com/your-username/devsweep/issues).*
