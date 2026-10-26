"""Every asset name the releases have carried lands in the kind that says who fetched it."""

import pytest

from release_stats.asset_kinds import asset_kind


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("SurfSense-Setup.exe", "installer_windows"),
        ("SurfSense-Setup-0.0.40.exe", "installer_windows"),
        ("SurfSense-Setup-0.0.14.1.exe", "installer_windows"),
        ("SurfSense-arm64.dmg", "installer_mac"),
        ("SurfSense-0.0.40-x64.dmg", "installer_mac"),
        ("SurfSense.AppImage", "installer_appimage"),
        ("SurfSense-0.0.40-x86_64.AppImage", "installer_appimage"),
        ("SurfSense.deb", "installer_deb"),
        ("SurfSense-0.0.40-amd64.deb", "installer_deb"),
        ("surfsense-local-electron_2.0.0_amd64.deb", "installer_deb"),
        ("SurfSense-arm64.zip", "update_zip_mac"),
        ("SurfSense-0.0.40-x64.zip", "update_zip_mac"),
        ("stable.yml", "manifest_stable_windows"),
        ("stable-mac.yml", "manifest_stable_mac"),
        ("stable-linux.yml", "manifest_stable_linux"),
        ("stable-linux-arm64.yml", "manifest_stable_linux"),
        ("latest.yml", "manifest_legacy_windows"),
        ("latest-mac.yml", "manifest_legacy_mac"),
        ("latest-linux.yml", "manifest_legacy_linux"),
        ("SurfSense-Setup.exe.blockmap", "blockmap"),
        ("SurfSense-arm64.zip.blockmap", "blockmap"),
        ("SurfSense.rpm", "installer_rpm"),
        ("SurfSense-0.0.40-x86_64.rpm", "installer_rpm"),
        ("SurfSense-0.0.20-x86_64.rpm", "installer_rpm"),
        ("install.sh", "install_script"),
        ("install.ps1", "install_script"),
        ("Packages", "apt_index"),
        ("Packages.gz", "apt_index"),
        ("Release", "apt_index"),
        ("Release.gpg", "apt_index"),
        ("InRelease", "apt_index"),
        ("surfsense-archive-keyring.gpg", "apt_index"),
        ("SHA256SUMS", "checksums"),
        ("SurfSense.snap", "other"),
        ("beta.yml", "other"),
        ("stable-windows.yml", "other"),
        ("checksums.txt", "other"),
    ],
)
def test_each_asset_name_has_the_kind_of_client_that_fetches_it(name, kind):
    assert asset_kind(name) == kind
