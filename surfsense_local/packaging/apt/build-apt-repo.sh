#!/usr/bin/env bash
# Builds the flat apt repository that sits next to SurfSense.deb on a release, so
#   deb [signed-by=/usr/share/keyrings/surfsense-archive-keyring.gpg] https://github.com/MODSetter/SurfSense/releases/latest/download/ ./
# resolves: Packages, Packages.gz, Release, InRelease, Release.gpg and that binary keyring.
#
#   APT_GPG_PRIVATE_KEY=<armored secret key> [APT_GPG_PASSPHRASE=<its passphrase>] \
#     build-apt-repo.sh <SurfSense.deb as uploaded> <out dir>
#
# Needs apt-ftparchive (apt-utils), gpg and gpgv. The key goes into a throwaway
# keyring, so a run by hand leaves yours as it was.
set -euo pipefail

if [ $# -ne 2 ]; then
  echo "usage: APT_GPG_PRIVATE_KEY=<armored secret key> $0 <SurfSense.deb> <out dir>" >&2
  exit 2
fi
DEB=$1
OUT=$2
if [ -z "${APT_GPG_PRIVATE_KEY:-}" ]; then
  echo "APT_GPG_PRIVATE_KEY is empty: apt refuses an unsigned repository" >&2
  exit 1
fi
if [ ! -f "$DEB" ]; then
  echo "no deb at $DEB" >&2
  exit 1
fi

WORK=$(mktemp -d)
export GNUPGHOME="$WORK/gnupg"
trap 'gpgconf --kill gpg-agent >/dev/null 2>&1 || true; rm -rf "$WORK"' EXIT
mkdir "$GNUPGHOME"
chmod 700 "$GNUPGHOME"

# gpg taking the passphrase, when the key has one, from fd 3 instead of a prompt.
keyed_gpg() {
  if [ -n "${APT_GPG_PASSPHRASE:-}" ]; then
    gpg --batch --pinentry-mode loopback --passphrase-fd 3 "$@" 3<<<"$APT_GPG_PASSPHRASE"
  else
    gpg --batch "$@"
  fi
}

printf '%s\n' "$APT_GPG_PRIVATE_KEY" | keyed_gpg --quiet --import
KEY=$(gpg --batch --with-colons --list-secret-keys | awk -F: '$1 == "fpr" { print $10; exit }')
if [ -z "$KEY" ]; then
  echo "APT_GPG_PRIVATE_KEY holds no secret key" >&2
  exit 1
fi

# The release asset's name, whatever the local file is called: Packages points at it.
mkdir "$WORK/pool" "$WORK/repo"
ln "$DEB" "$WORK/pool/SurfSense.deb" 2>/dev/null || cp "$DEB" "$WORK/pool/SurfSense.deb"
(cd "$WORK/pool" && apt-ftparchive packages .) > "$WORK/repo/Packages"
if ! grep -qx 'Filename: ./SurfSense.deb' "$WORK/repo/Packages"; then
  echo "Packages does not point at ./SurfSense.deb:" >&2
  cat "$WORK/repo/Packages" >&2
  exit 1
fi
gzip -9 -n -c "$WORK/repo/Packages" > "$WORK/repo/Packages.gz"

# Written outside repo/: apt-ftparchive would otherwise hash the half-written Release too.
apt-ftparchive \
  -o APT::FTPArchive::Release::Origin=SurfSense \
  -o APT::FTPArchive::Release::Label=SurfSense \
  release "$WORK/repo" > "$WORK/Release"
mv "$WORK/Release" "$WORK/repo/Release"

keyed_gpg --local-user "$KEY" --digest-algo SHA512 --clearsign \
  --output "$WORK/repo/InRelease" "$WORK/repo/Release"
keyed_gpg --local-user "$KEY" --digest-algo SHA512 --armor --detach-sign \
  --output "$WORK/repo/Release.gpg" "$WORK/repo/Release"
gpg --batch --export-options export-minimal --export "$KEY" > "$WORK/repo/surfsense-archive-keyring.gpg"

# As apt will check them: against the published keyring alone.
gpgv --keyring "$WORK/repo/surfsense-archive-keyring.gpg" "$WORK/repo/InRelease"
gpgv --keyring "$WORK/repo/surfsense-archive-keyring.gpg" "$WORK/repo/Release.gpg" "$WORK/repo/Release"

mkdir -p "$OUT"
cp "$WORK/repo/"{Packages,Packages.gz,Release,InRelease,Release.gpg,surfsense-archive-keyring.gpg} "$OUT/"
