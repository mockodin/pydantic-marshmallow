# Release Workflow Setup

This document explains how to configure the repository for automated releases using semantic-release.

## Problem

The release workflow needs to commit version updates (CHANGELOG.md, pyproject.toml) back to the protected `main` branch. By default, the `GITHUB_TOKEN` provided to workflows cannot bypass branch protection rules.

## Solution Options

### Option 1: Use a Personal Access Token (PAT) with Bypass Permissions (Recommended)

1. **Create a Fine-Grained PAT**:
   - Go to GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens
   - Click "Generate new token"
   - Set repository access to "Only select repositories" → Choose this repository
   - Under "Permissions", grant:
     - Contents: Read and write
     - Pull requests: Read and write (optional, for PR creation)
     - Workflows: Read and write (if modifying workflows)
   - **Important**: The account owning this PAT must have admin access to bypass branch protection

2. **Add the PAT as a Repository Secret**:
   - Go to Repository Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `GH_TOKEN`
   - Value: The PAT created above

3. **The workflow is already configured** to use `GH_TOKEN` if available, falling back to `GITHUB_TOKEN`

### Option 2: Configure Branch Protection to Allow the GitHub Actions Bot

1. Go to Repository Settings → Branches → Branch protection rules for `main`
2. Check "Allow specified actors to bypass required pull requests"
3. Add `github-actions[bot]` as an allowed actor
4. Save changes

**Note**: This option is less secure as it allows all GitHub Actions workflows to bypass protection.

### Option 3: Use GitHub App (Most Secure, More Complex)

Create a GitHub App with permissions to bypass branch protection and use it in the workflow. This is the most secure option but requires more setup. See [GitHub's documentation](https://docs.github.com/en/apps/creating-github-apps) for details.

### Option 4: No Auto-Commit (Tags Only)

If you prefer not to commit version updates back to main:

1. Remove the `@semantic-release/git`, `@semantic-release/changelog`, and `@semantic-release/exec` plugins from `.releaserc.json`
2. The workflow will only create GitHub releases and tags
3. Version bumping can be handled manually or through PRs

## Current Configuration

The workflow is configured to:
- Use `GH_TOKEN` secret if available (Option 1)
- Fall back to `GITHUB_TOKEN` if `GH_TOKEN` is not set
- Use `persist-credentials: false` to allow custom token usage

## Testing the Release Workflow

1. After configuring one of the options above, trigger the workflow manually:
   ```bash
   gh workflow run release.yml
   ```

2. Or use dry-run mode to test without actually releasing:
   ```bash
   gh workflow run release.yml -f dry_run=true
   ```

## Troubleshooting

### Error: "GH006: Protected branch update failed"

**Cause**: The token being used doesn't have permission to bypass branch protection.

**Solution**: Implement Option 1 (PAT) or Option 2 (Allow GitHub Actions bot) above.

### Error: "Resource not accessible by integration"

**Cause**: The token doesn't have the required permissions.

**Solution**: Check that your PAT has the correct permissions (Contents: Read and write).

### Releases are created but CHANGELOG.md is not updated

**Cause**: The `@semantic-release/git` plugin is not configured or the token doesn't have write permissions.

**Solution**: Check that `.releaserc.json` includes the git plugin and that your token has write permissions.
