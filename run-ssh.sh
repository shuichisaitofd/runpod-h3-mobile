#!/usr/bin/env bash
set -Eeuo pipefail

mkdir -p /run/sshd /root/.ssh
chmod 700 /root/.ssh

KEY_MATERIAL="${SSH_PUBLIC_KEY:-${PUBLIC_KEY:-}}"
if [ -n "$KEY_MATERIAL" ]; then
  printf '%s\n' "$KEY_MATERIAL" > /root/.ssh/authorized_keys
  chmod 600 /root/.ssh/authorized_keys
  echo "[H3][SSH] Public key installed for root."
else
  echo "[H3][SSH][WARN] No SSH_PUBLIC_KEY/PUBLIC_KEY was provided; Full SSH key login may fail."
fi

ssh-keygen -A >/dev/null 2>&1 || true
/usr/sbin/sshd

echo "[H3][SSH] sshd started on TCP 22."

exec /run-h3.sh "$@"
