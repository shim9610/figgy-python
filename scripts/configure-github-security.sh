#!/usr/bin/env bash
# Run locally with a GitHub CLI identity that administers this repository.
# No credentials are embedded, and main-branch protection is configured separately.
set -euo pipefail
repository=${1:-shim9610/figgy-python}
if [[ ! "$repository" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
    echo "Expected owner/repository, got: $repository" >&2
    exit 1
fi
if [ "$(gh api "repos/$repository" --jq '.permissions.admin')" != true ]; then
    echo "The active GitHub CLI identity must administer $repository" >&2
    exit 1
fi
gh repo edit "$repository" --description 'NumPy-first plotting with Rust: interactive native windows and browser WebGPU notebooks.'
gh api --method PUT "repos/$repository/private-vulnerability-reporting"
gh api --method PUT "repos/$repository/vulnerability-alerts"
gh api --silent --method PATCH "repos/$repository" --input - <<'JSON'
{
  "security_and_analysis": {
    "secret_scanning": {"status": "enabled"},
    "secret_scanning_push_protection": {"status": "enabled"}
  }
}
JSON
gh api "repos/$repository" --jq '{description, security_and_analysis}'
gh api "repos/$repository/private-vulnerability-reporting"
gh api "repos/$repository/vulnerability-alerts"
echo 'Repository description, private reports, Dependabot alerts and secret protection configured.'
