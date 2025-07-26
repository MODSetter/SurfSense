# Pre-commit Hooks for SurfSense Contributors

Welcome to SurfSense! As an open-source project, we use pre-commit hooks to maintain code quality, security, and consistency across our multi-component codebase. This guide will help you set up and work with our pre-commit configuration.

## 🚀 What is Pre-commit?

Pre-commit is a framework for managing multi-language pre-commit hooks. It runs automatically before each commit to catch issues early, ensuring high code quality and consistency across the project.

## 📁 Project Structure

SurfSense consists of three main components:
- **`surfsense_backend/`** - Python backend API
- **`surfsense_web/`** - Next.js web application  
- **`surfsense_browser_extension/`** - TypeScript browser extension

## 🛠 Installation

### Prerequisites
- Python 3.8 or higher
- Node.js 18+ and pnpm (for frontend components)
- Git

### Install Pre-commit

```bash
# Install pre-commit globally
pip install pre-commit

# Or using your preferred package manager
# pipx install pre-commit  # Recommended for isolation
```

### Setup Pre-commit Hooks

1. **Clone the repository**:
   ```bash
   git clone https://github.com/masabinhok/SurfSense.git
   cd SurfSense
   ```

2. **Install the pre-commit hooks**:
   ```bash
   pre-commit install
   ```

3. **Install commit message hooks** (optional, for conventional commits):
   ```bash
   pre-commit install --hook-type commit-msg
   ```

## 🔧 Configuration Files Added

When you install pre-commit, the following files are part of the setup:

- **`.pre-commit-config.yaml`** - Main pre-commit configuration
- **`.secrets.baseline`** - Baseline file for secret detection (prevents false positives)
- **`.github/workflows/pre-commit.yml`** - CI workflow that runs pre-commit on PRs

## 🎯 What Gets Checked

### All Files
- ✅ Trailing whitespace removal
- ✅ YAML, JSON, and TOML validation
- ✅ Large file detection (>10MB)
- ✅ Merge conflict markers
- 🔒 **Secret detection** using detect-secrets

### Python Backend (`surfsense_backend/`)
- 🐍 **Black** - Code formatting
- 📦 **isort** - Import sorting
- ⚡ **Ruff** - Fast linting and formatting
- 🔍 **MyPy** - Static type checking
- 🛡️ **Bandit** - Security vulnerability scanning

### Frontend (`surfsense_web/` & `surfsense_browser_extension/`)
- 💅 **Prettier** - Code formatting
- 🔍 **ESLint** - Linting (Next.js config)
- 📝 **TypeScript** - Compilation checks

### Commit Messages
- 📝 **Commitizen** - Conventional commit format validation

## 🚀 Usage

### Normal Workflow
Pre-commit will run automatically when you commit:

```bash
git add .
git commit -m "feat: add new feature"
# Pre-commit hooks will run automatically
```

### Manual Execution

Run on staged files only:
```bash
pre-commit run
```

Run on specific files:
```bash
pre-commit run --files path/to/file.py path/to/file.ts
```

Run all hooks on all files:
```bash
pre-commit run --all-files
```

⚠️ **Warning**: Running `--all-files` may generate numerous errors as this codebase has existing linting and type issues that are being gradually resolved.

### Advanced Commands

Update all hooks to latest versions:
```bash
pre-commit autoupdate
```

Run only specific hooks:
```bash
pre-commit run black                    # Run only black
pre-commit run --all-files prettier     # Run prettier on all files
```

Clean pre-commit cache:
```bash
pre-commit clean
```

## 🆘 Bypassing Pre-commit (When Necessary)

Sometimes you might need to bypass pre-commit hooks (use sparingly!):

### Skip all hooks for one commit:
```bash
git commit -m "fix: urgent hotfix" --no-verify
```

### Skip specific hooks:
```bash
SKIP=mypy,black git commit -m "feat: work in progress"
```

Available hook IDs to skip:
- `trailing-whitespace`, `check-yaml`, `check-json`
- `detect-secrets`
- `black`, `isort`, `ruff`, `ruff-format`, `mypy`, `bandit`  
- `prettier`, `eslint`
- `typescript-check-web`, `typescript-check-extension`
- `commitizen`

## 🐛 Common Issues & Solutions

### Secret Detection False Positives

If detect-secrets flags legitimate content as secrets:

1. **Review the detection** - Ensure it's not actually a secret
2. **Update baseline**:
   ```bash
   detect-secrets scan --baseline .secrets.baseline --update
   git add .secrets.baseline
   ```

### TypeScript/Node.js Issues

Ensure dependencies are installed:
```bash
cd surfsense_web && pnpm install
cd surfsense_browser_extension && pnpm install
```

### Python Environment Issues

For Python hooks, ensure you're in the correct environment:
```bash
cd surfsense_backend
# If using uv
uv sync
# Or traditional pip
pip install -r requirements.txt
```

### Hook Installation Issues

If hooks aren't running:
```bash
pre-commit uninstall
pre-commit install --install-hooks
```

## 📊 Performance Tips

- **Incremental runs**: Pre-commit only runs on changed files by default
- **Parallel execution**: Many hooks run in parallel for speed
- **Caching**: Pre-commit caches environments to speed up subsequent runs

## 🔄 CI Integration

Pre-commit also runs in our GitHub Actions CI pipeline on every PR to `main`. The CI:
- Runs only on changed files for efficiency
- Provides the same feedback as local pre-commit
- Prevents merging code that doesn't pass quality checks

## 📋 Best Practices

1. **Install pre-commit early** in your development setup
2. **Fix issues incrementally** rather than bypassing hooks
3. **Update your branch regularly** to avoid conflicts with formatting changes
4. **Run `--all-files` periodically** on feature branches (in small chunks)
5. **Keep the `.secrets.baseline` updated** when legitimate secrets-like strings are added

## 💡 Contributing to Pre-commit Config

To modify the pre-commit configuration:

1. Edit `.pre-commit-config.yaml`
2. Test your changes:
   ```bash
   pre-commit run --all-files  # Test with caution!
   ```
3. Update the baseline if needed:
   ```bash
   detect-secrets scan --baseline .secrets.baseline --update
   ```
4. Submit a PR with your changes

## 🆘 Getting Help

- **Pre-commit docs**: https://pre-commit.com/
- **Project issues**: Open an issue on GitHub
- **Hook-specific help**: Check individual tool documentation (Black, Ruff, ESLint, etc.)

---

Thank you for contributing to SurfSense! 🏄‍♀️ Quality code makes everyone's surfing experience smoother.