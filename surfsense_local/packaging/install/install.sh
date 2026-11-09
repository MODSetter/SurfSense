#!/bin/sh
# Installs the SurfSense desktop app from its GitHub release:
#
#   curl -fsSL https://www.surfsense.com/install.sh | sh
#
# macOS on Apple Silicon: the app goes to /Applications (or ~/Applications),
# once Gatekeeper accepts it. Linux x86_64 with glibc 2.35 or later: the signed
# apt repository, the rpm through dnf or zypper, or else, image-based systems
# included, the AppImage in ~/Applications. Every file is checked against the
# release's SHA256SUMS first. Nothing is sent anywhere but the downloads
# themselves.
#
#   SURFSENSE_VERSION=2.2.4      install that release instead of the latest, even an older one
#   SURFSENSE_APT_REPO=0         with apt, install the .deb without adding the repository
#   SURFSENSE_INSTALL_DRY_RUN=1  print the plan; download, ask for and change nothing
#
# A dry run also takes SURFSENSE_FAKE_OS, _ARCH, _GLIBC (a version or none),
# _PKG (apt, dnf, zypper or none), or _ON_PATH (such as "apt-get dnf", or none)
# and _LIBC_DB (dpkg, rpm or none) to choose it, _IMAGE_BASED (1 or 0), or
# _OSTREE_BOOTED (1 or 0) and _MOUNTS (the text of /proc/mounts) to decide it,
# _APT_REPO (1 or 0), _APPLICATIONS_WRITABLE (1 or 0) and _LATEST (a tag) in
# place of this machine and GitHub, so install-scripts.test.mjs can walk every
# branch offline.

set -eu

REPO="https://github.com/MODSetter/SurfSense"
DOWNLOADS_PAGE="https://www.surfsense.com/downloads"
APT_KEYRING=/usr/share/keyrings/surfsense-archive-keyring.gpg
APT_SOURCE=/etc/apt/sources.list.d/surfsense.list
APT_LINE="deb [signed-by=$APT_KEYRING] $REPO/releases/latest/download/ ./"
DEB_PACKAGE=surfsense-local-electron
KEYRING_FILE=surfsense-archive-keyring.gpg

say() { printf 'SurfSense: %s\n' "$*"; }
finish() {
  if [ "$DRY_RUN" = 1 ]; then say "A real run would end with: $*"; else say "$*"; fi
}
fail() {
  printf 'SurfSense: %s\n' "$*" >&2
  exit 1
}

# In a dry run, prints SURFSENSE_FAKE_<name> in place of what this machine says.
fake() {
  [ "$DRY_RUN" = 1 ] || return 1
  eval "fake_value=\${SURFSENSE_FAKE_$1:-}"
  [ -n "$fake_value" ] || return 1
  printf '%s\n' "$fake_value"
}

# Under `curl ... | sh` stdin is the rest of this script, so no command reads it.
run() {
  if [ "$DRY_RUN" = 1 ]; then
    printf '  would run: %s\n' "$*"
  else
    "$@" </dev/null
  fi
}

as_root() {
  if [ "$DRY_RUN" = 0 ] && [ "$(id -u)" = 0 ]; then
    run "$@"
  else
    run sudo "$@"
  fi
}

can_be_root() {
  [ "$DRY_RUN" = 1 ] || [ "$(id -u)" = 0 ] || command -v sudo >/dev/null 2>&1
}

write_file() {
  if [ "$DRY_RUN" = 1 ]; then
    printf '  would write %s:\n' "$1"
    printf '%s\n' "$2" | sed 's/^/    /'
  else
    printf '%s\n' "$2" >"$1"
  fi
}

machine_os() { fake OS || uname -s; }

machine_arch() {
  fake ARCH && return
  # A shell under Rosetta reports x86_64 on Apple Silicon.
  if [ "$(uname -s)" = Darwin ] && [ "$(sysctl -n hw.optional.arm64 2>/dev/null || true)" = 1 ]; then
    echo arm64
  else
    uname -m
  fi
}

on_path() {
  if listed=$(fake ON_PATH); then
    case " $listed " in *" $1 "*) return 0 ;; *) return 1 ;; esac
  fi
  command -v "$1" >/dev/null 2>&1
}

# Whether the C library this system runs on is in $1's package database.
libc_from() {
  if libc_db=$(fake LIBC_DB); then
    [ "$libc_db" = "$1" ]
    return
  fi
  case $1 in
    dpkg) dpkg-query -W libc6 >/dev/null 2>&1 ;;
    rpm) rpm -q glibc >/dev/null 2>&1 ;;
  esac
}

# The first of apt, dnf and zypper that installs this system's own packages:
# Arch, say, may carry apt or dnf for mkosi, which would add another
# distribution's repository there.
package_manager() {
  fake PKG && return
  for manager in apt-get dnf zypper; do
    on_path "$manager" || continue
    if [ "$manager" = apt-get ]; then db=dpkg; else db=rpm; fi
    if libc_from "$db"; then
      echo "${manager%-get}"
      return
    fi
  done
  echo none
}

# ostree and bootc hosts (Bazzite, Bluefin, Aurora), openSUSE's transactional
# ones (Aeon, Kalpa, MicroOS) and ABRoot ones (Vanilla OS) may carry a package
# manager that cannot install onto their read-only system. The root's mount
# says so whatever is on PATH, which for an ordinary user may lack the
# /usr/sbin that holds transactional-update. /proc/mounts, not [ -w / ], which
# no ordinary user passes; its last / is the one in effect.
image_based() {
  if value=$(fake IMAGE_BASED); then
    [ "$value" = 1 ]
    return
  fi
  if value=$(fake OSTREE_BOOTED); then
    [ "$value" = 1 ] && return
  elif [ -e /run/ostree-booted ]; then
    return
  fi
  { fake MOUNTS || cat /proc/mounts; } 2>/dev/null |
    awk '$2 == "/" { ro = 0; n = split($4, opts, ","); for (i = 1; i <= n; i++) if (opts[i] == "ro") ro = 1 }
      END { exit !ro }'
}

# Prints nothing on a system without glibc, such as musl's.
glibc_version() {
  version=$(fake GLIBC) ||
    version=$(getconf GNU_LIBC_VERSION 2>/dev/null | awk '{ print $2 }')
  [ -n "$version" ] || version=$(ldd --version 2>/dev/null | awk 'NR == 1 { print $NF; exit }')
  case $version in [0-9]*.[0-9]*) printf '%s\n' "$version" ;; esac
}

applications_writable() {
  fake APPLICATIONS_WRITABLE && return
  if [ -w /Applications ]; then echo 1; else echo 0; fi
}

pick_tools() {
  [ "$DRY_RUN" = 1 ] && return
  if command -v curl >/dev/null 2>&1; then
    downloader=curl
  elif command -v wget >/dev/null 2>&1; then
    downloader=wget
  else
    fail "Needs curl or wget to download the installer."
  fi
  for tool in sha256sum shasum openssl; do
    if command -v "$tool" >/dev/null 2>&1; then
      hasher=$tool
      return
    fi
  done
  fail "Needs sha256sum, shasum or openssl to check the download."
}

# The case rejects a newline too, which grep would read as a second line.
is_release_tag() {
  case $1 in *[!v0-9.]*) return 1 ;; esac
  printf '%s\n' "$1" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+$'
}

# One tag for every download, so SHA256SUMS and the installer always match even
# when a release is published between the two requests.
resolve_tag() {
  if [ -n "${SURFSENSE_VERSION:-}" ]; then
    tag="v${SURFSENSE_VERSION#v}"
  elif [ "$DRY_RUN" = 1 ]; then
    tag=${SURFSENSE_FAKE_LATEST:-"<latest>"}
    say "Would ask $REPO/releases/latest which release is the latest."
  elif [ "$downloader" = curl ]; then
    latest=$(curl -fsSIL -o /dev/null -w '%{url_effective}' --proto '=https' "$REPO/releases/latest") ||
      fail "Could not reach GitHub to find the latest release."
    tag=${latest##*/releases/tag/}
  else
    tag=$(wget -S --spider "$REPO/releases/latest" 2>&1 |
      sed -n 's#^ *Location: .*/releases/tag/\([^[:space:]]*\).*#\1#p' | tail -n 1 | tr -d '\r')
  fi
  if [ "$tag" != "<latest>" ] && ! is_release_tag "$tag"; then
    if [ -n "${SURFSENSE_VERSION:-}" ]; then
      fail "SURFSENSE_VERSION must be a release number such as 2.2.4, not '$SURFSENSE_VERSION'."
    fi
    fail "Could not tell which release is the latest from GitHub's answer ('$tag')."
  fi
  say "Installing SurfSense $tag."
}

make_workdir() {
  # /var/tmp, not /tmp: the installers are over 1 GB and /tmp is often in RAM.
  base=${TMPDIR:-/var/tmp}
  base=${base%/}
  if [ "$DRY_RUN" = 1 ]; then
    work="$base/surfsense-install.XXXXXX"
    return
  fi
  work=$(mktemp -d "$base/surfsense-install.XXXXXX")
  trap cleanup EXIT
  trap 'exit 1' INT TERM
}

cleanup() {
  rm -rf "$work"
  if [ -n "${staging:-}" ]; then rm -rf "$staging"; fi
}

download() {
  if [ "$DRY_RUN" = 1 ]; then
    printf '  would download %s\n' "$REPO/releases/download/$tag/$1"
    return
  fi
  say "Downloading $1."
  got=0
  if [ "$downloader" = curl ]; then
    curl -fL --proto '=https' --tlsv1.2 --retry 3 --progress-bar -o "$work/$1" "$REPO/releases/download/$tag/$1" || got=$?
  else
    wget -O "$work/$1" "$REPO/releases/download/$tag/$1" || got=$?
  fi
  # curl -f exits 22 and wget 8 when GitHub answers with an error, such as a 404.
  if [ "$1" = SHA256SUMS ] && { [ "$got" = 22 ] || [ "$got" = 8 ]; }; then
    fail "$tag has no SHA256SUMS to check the installer against, so nothing was installed. See $DOWNLOADS_PAGE"
  fi
  [ "$got" = 0 ] || fail "Could not download $1 from $tag."
}

listed_sha256() {
  awk -v name="$1" '{ sub(/\r$/, "") }
    length($1) == 64 && ($2 == name || $2 == "*" name) { print tolower($1); found = 1; exit }
    END { exit !found }' "$work/SHA256SUMS"
}

file_sha256() {
  case $hasher in
    sha256sum) sha256sum "$1" | awk '{ print tolower($1) }' ;;
    shasum) shasum -a 256 "$1" | awk '{ print tolower($1) }' ;;
    openssl) openssl dgst -sha256 "$1" | awk '{ print tolower($NF) }' ;;
  esac
}

download_checked() {
  download "$1"
  if [ "$DRY_RUN" = 1 ]; then
    printf '  would check %s against SHA256SUMS\n' "$1"
    return
  fi
  expected=$(listed_sha256 "$1") || fail "SHA256SUMS on $tag does not list $1, so it was not installed."
  [ "$(file_sha256 "$work/$1")" = "$expected" ] ||
    fail "$1 does not match its SHA-256 in SHA256SUMS, so it was not installed."
  say "$1 matches SHA256SUMS."
}

# The release job lists the apt files in SHA256SUMS once it has signed them.
tag_has_apt_repo() {
  if [ "$DRY_RUN" = 1 ]; then
    [ "${SURFSENSE_FAKE_APT_REPO:-1}" = 1 ]
    return
  fi
  listed_sha256 InRelease >/dev/null && listed_sha256 "$KEYRING_FILE" >/dev/null
}

install_mac() {
  download SHA256SUMS
  download_checked SurfSense-arm64.zip
  if [ "$(applications_writable)" = 1 ]; then
    dest=/Applications
  else
    dest="$HOME/Applications"
    say "/Applications is not writable for $(id -un 2>/dev/null || echo this user), so SurfSense goes to $dest."
    run mkdir -p "$dest"
  fi
  if [ "$DRY_RUN" = 0 ] && pgrep -x SurfSense >/dev/null 2>&1; then
    fail "SurfSense is running. Quit it, then run this again."
  fi

  # Unpacked beside its destination, so the move into place is a rename.
  if [ "$DRY_RUN" = 1 ]; then
    staging="$dest/.surfsense-install.XXXXXX"
  else
    staging=$(mktemp -d "$dest/.surfsense-install.XXXXXX")
  fi
  run ditto -x -k "$work/SurfSense-arm64.zip" "$staging"
  if [ "$DRY_RUN" = 1 ]; then
    printf '  would run: spctl --assess --type execute --verbose=2 %s\n' "$staging/SurfSense.app"
  elif verdict=$(spctl --assess --type execute --verbose=2 "$staging/SurfSense.app" 2>&1); then
    printf '%s\n' "$verdict"
  else
    printf '%s\n' "$verdict" >&2
    fail "Gatekeeper did not accept this SurfSense.app, so it was not installed."
  fi

  # The previous app waits in staging until the new one is in place, then goes with it.
  if [ -e "$dest/SurfSense.app" ]; then
    run mv "$dest/SurfSense.app" "$staging/previous.app"
    if ! run mv "$staging/SurfSense.app" "$dest/SurfSense.app"; then
      run mv "$staging/previous.app" "$dest/SurfSense.app"
      fail "Could not move the new SurfSense.app into $dest; the previous one is back in place."
    fi
  else
    run mv "$staging/SurfSense.app" "$dest/SurfSense.app"
  fi
  finish "Installed $dest/SurfSense.app. Open it from Launchpad, or: open \"$dest/SurfSense.app\""
}

install_from_apt_repo() {
  download_checked "$KEYRING_FILE"
  write_file "$work/surfsense.list" "$APT_LINE"
  say "Adding the apt repository needs root: sudo writes $APT_KEYRING and $APT_SOURCE, then runs apt-get."
  as_root install -m 0644 "$work/$KEYRING_FILE" "$APT_KEYRING"
  as_root install -m 0644 "$work/surfsense.list" "$APT_SOURCE"
  as_root apt-get update ||
    fail "apt-get update failed; the SurfSense source is in $APT_SOURCE. Fix the error above, then: sudo apt-get update && sudo apt-get install $DEB_PACKAGE"
  as_root apt-get install -y "$DEB_PACKAGE"
  finish "Installed $DEB_PACKAGE. apt upgrades it from now on: sudo apt-get update && sudo apt-get upgrade"
}

install_deb() {
  download_checked SurfSense.deb
  # apt reads a local package as its _apt user, which cannot enter a 0700 folder.
  run chmod 0755 "$work"
  say "Installing the .deb needs root: sudo runs apt-get install."
  # A pinned release may be older than the installed one, which apt -y refuses.
  as_root apt-get install -y ${SURFSENSE_VERSION:+--allow-downgrades} "$work/SurfSense.deb"
  finish "Installed $DEB_PACKAGE from SurfSense.deb."
}

install_with_apt() {
  download SHA256SUMS
  if [ "${SURFSENSE_APT_REPO:-1}" = 0 ]; then
    say "SURFSENSE_APT_REPO=0, so the .deb is installed without the apt repository."
    install_deb
  elif [ -n "${SURFSENSE_VERSION:-}" ]; then
    say "The apt repository serves only the latest release, so $tag is installed from its .deb."
    install_deb
  elif tag_has_apt_repo; then
    install_from_apt_repo
  else
    say "$tag carries no apt repository, so SurfSense is installed from its .deb."
    install_deb
  fi
}

# The rpm is not signed; SHA256SUMS, fetched over HTTPS from the release, is its check.
install_rpm() {
  download SHA256SUMS
  download_checked SurfSense.rpm
  say "Installing the rpm needs root: sudo runs $1."
  # dnf installs an exact local rpm over a newer one; zypper skips it, exiting 0, without --oldpackage.
  if [ "$1" = dnf ]; then
    as_root dnf install -y "$work/SurfSense.rpm"
  else
    as_root zypper --non-interactive install --allow-unsigned-rpm ${SURFSENSE_VERSION:+--oldpackage} "$work/SurfSense.rpm"
  fi
  finish "Installed SurfSense from SurfSense.rpm."
}

install_appimage() {
  download SHA256SUMS
  download_checked SurfSense.AppImage
  apps="$HOME/Applications"
  data=${XDG_DATA_HOME:-"$HOME/.local/share"}
  icon_line=
  run mkdir -p "$apps" "$data/applications"
  run chmod 0755 "$work/SurfSense.AppImage"
  if [ "$DRY_RUN" = 1 ]; then
    printf '  would copy the icons inside the AppImage to %s\n' "$data/icons/hicolor"
    icon_line="Icon=surfsense-local"
  elif (cd "$work" && ./SurfSense.AppImage --appimage-extract usr/share/icons/hicolor >/dev/null 2>&1) &&
    [ -d "$work/squashfs-root/usr/share/icons/hicolor" ]; then
    mkdir -p "$data/icons"
    cp -R "$work/squashfs-root/usr/share/icons/hicolor" "$data/icons/"
    icon_line="Icon=surfsense-local"
  fi
  run mv "$work/SurfSense.AppImage" "$apps/SurfSense.AppImage"
  write_file "$data/applications/surfsense-appimage.desktop" "[Desktop Entry]
Type=Application
Name=SurfSense
Comment=Local-first research over your own documents
Exec=\"$apps/SurfSense.AppImage\" %U
$icon_line
Terminal=false
Categories=Office;Utility;
StartupWMClass=SurfSense"
  if [ "$DRY_RUN" = 0 ] && command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$data/applications" >/dev/null 2>&1 || true
  fi
  finish "Installed $apps/SurfSense.AppImage, with SurfSense in your app menu."
}

install_linux() {
  pkg=$(package_manager)
  if [ "$pkg" != none ] && image_based; then
    say "This is an image-based system, where $pkg cannot install a package, so SurfSense is installed as an AppImage instead."
    pkg=none
  elif [ "$pkg" != none ] && ! can_be_root; then
    say "A system package needs root and sudo is missing, so SurfSense is installed as an AppImage instead."
    pkg=none
  fi
  case $pkg in
    apt) install_with_apt ;;
    dnf | zypper) install_rpm "$pkg" ;;
    *) install_appimage ;;
  esac
}

# Everything runs from here, so a download cut off midway runs nothing.
main() {
  DRY_RUN=0
  if [ "${SURFSENSE_INSTALL_DRY_RUN:-0}" = 1 ]; then
    DRY_RUN=1
    say "Dry run: nothing is downloaded, changed or installed."
  fi

  os=$(machine_os)
  arch=$(machine_arch)
  case $os in
    Darwin)
      [ "$arch" = arm64 ] ||
        fail "SurfSense for macOS needs Apple Silicon (M1 or later); this Mac is $arch. See $DOWNLOADS_PAGE"
      ;;
    Linux)
      case $arch in
        x86_64 | amd64) ;;
        *) fail "SurfSense for Linux is built for x86_64 only; this machine is $arch. See $DOWNLOADS_PAGE" ;;
      esac
      # Every Linux build needs glibc 2.35. The deb declares libc6 (>= 2.35), but the rpm and
      # the AppImage do not, so dnf, zypper or the AppImage would install anyway without this.
      glibc=$(glibc_version)
      printf '%s\n' "$glibc" | awk -F. '$1 + 0 > 2 || ($1 + 0 == 2 && $2 + 0 >= 35) { ok = 1 } END { exit !ok }' ||
        fail "SurfSense for Linux needs glibc 2.35 or later (Ubuntu 22.04, Debian 12, current Fedora, EL10); this machine has ${glibc:+glibc }${glibc:-no glibc}. See $DOWNLOADS_PAGE"
      ;;
    *)
      fail "This script installs SurfSense on macOS and Linux, not $os. See $DOWNLOADS_PAGE (on Windows: irm https://www.surfsense.com/install.ps1 | iex)"
      ;;
  esac

  pick_tools
  resolve_tag
  make_workdir
  if [ "$os" = Darwin ]; then install_mac; else install_linux; fi
}

main "$@"
