#!/bin/sh
# Run once (from the repo root, e.g. in Git Bash):   sh scripts/install-hooks.sh
# Installs a git pre-commit hook that runs scripts/check_secrets.py and refuses commits containing secrets.
cat > .git/hooks/pre-commit <<'HOOK'
#!/bin/sh
cd "$(git rev-parse --show-toplevel)" || exit 1
python scripts/check_secrets.py || exit 1
HOOK
chmod +x .git/hooks/pre-commit
echo "pre-commit secrets check installed"
