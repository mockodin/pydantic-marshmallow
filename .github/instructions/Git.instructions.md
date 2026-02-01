# Git and CI/CD Instructions

## Pre-Push Verification

**Always run before pushing:**

```bash
# Run all checks
pytest tests/ -v
mypy src/pydantic_marshmallow/
ruff check src/ tests/
```

**DO NOT push if any check fails.**

## Branching Strategy

1. **Create feature branch** from `main`:
   ```bash
   git checkout -b feat/feature-name
   ```

2. **Make atomic commits** with conventional commit messages:
   ```
   feat: add new type mapping for X
   fix: handle edge case in Y
   test: add tests for Z
   docs: update README
   chore: update dependencies
   ```

3. **Push and create PR** for review

## Merge Policy

**Before merging any PR to `main`:**

1. **Push changes** - Never merge uncommitted work
2. **Wait for CI** - Check GitHub Actions status
3. **All checks must pass**:
   - Tests pass on Python 3.9, 3.10, 3.11, 3.12, 3.13, 3.14
   - mypy type checking passes
   - ruff and flake8 linting passes
4. **Only merge after CI success** - The `ci-passed` job gates all merges

## Checking CI Status

```bash
# Using GitHub CLI
gh run list --workflow ci.yml --branch $(git branch --show-current) --limit 1

# Wait for run to complete
gh run watch <run-id>

# Check if run succeeded
gh run view <run-id> --exit-status
```

## Never Do

- ❌ Merge to main without pushing first
- ❌ Merge while CI is still running
- ❌ Merge when CI has failed
- ❌ Force push to main
- ❌ Bypass CI checks

## Always Do

- ✅ Run tests locally before pushing
- ✅ Use conventional commit messages
- ✅ Push changes and wait for CI
- ✅ Verify all tests pass
- ✅ Only merge after CI passes

## Conventional Commits

| Prefix | Use Case |
|:-------|:---------|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `test:` | Adding/updating tests |
| `docs:` | Documentation changes |
| `chore:` | Maintenance, dependencies |
| `refactor:` | Code restructuring |
| `perf:` | Performance improvements |
