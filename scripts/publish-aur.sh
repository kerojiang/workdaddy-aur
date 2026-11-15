#!/usr/bin/env bash
# Publish the tracked package files to ssh://aur@aur.archlinux.org/workdaddy-bin.git
# Designed for GitHub Actions: the private key comes from the AUR_SSH_PRIVATE_KEY secret.
set -euo pipefail

version="${1:-unknown}"
: "${AUR_SSH_PRIVATE_KEY:?secret AUR_SSH_PRIVATE_KEY is not configured}"

pkgname=workdaddy-bin
aur_user="${AUR_USERNAME:-jiangjie}"
aur_email="${AUR_EMAIL:-kero_jiang@126.com}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ssh_dir="${HOME}/.ssh"
install -d -m 700 "$ssh_dir"
key_file="$ssh_dir/aur_automation"
printf '%s\n' "$AUR_SSH_PRIVATE_KEY" > "$key_file"
chmod 600 "$key_file"

cat > "$ssh_dir/config" <<EOF
Host aur.archlinux.org
  User aur
  IdentityFile $key_file
  IdentitiesOnly yes
  StrictHostKeyChecking yes
EOF

# Pinned host key (ssh-keyscan -t ed25519 aur.archlinux.org, verified twice locally).
cat > "$ssh_dir/known_hosts" <<'EOF'
aur.archlinux.org ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEuBKrPzbawxA/k2g6NcyV5jmqwJ2s+zpgZGZ7tpLIcN
EOF
chmod 600 "$ssh_dir/known_hosts"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

echo "==> cloning AUR repository for $pkgname"
git -c init.defaultBranch=master clone \
  "ssh://aur@aur.archlinux.org/${pkgname}.git" "$work/aur"

for file in PKGBUILD .SRCINFO LICENSE LICENSE.upstream; do
  cp "$repo_root/$file" "$work/aur/$file"
done

cd "$work/aur"
git config user.name "$aur_user"
git config user.email "$aur_email"
git add -f PKGBUILD .SRCINFO LICENSE LICENSE.upstream

if git rev-parse --verify HEAD >/dev/null 2>&1 && git diff --cached --quiet; then
  echo "==> AUR already matches local files (version $version); nothing to push"
  exit 0
fi

git commit -m "Update to $version"
git push origin master
echo "==> pushed $pkgname $version to AUR"
