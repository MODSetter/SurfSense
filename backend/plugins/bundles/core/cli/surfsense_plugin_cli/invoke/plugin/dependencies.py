"""Installs the plugin's dependencies beside it before a run, only when they changed."""

import hashlib
import shutil
import tempfile
from pathlib import Path

import typer

from surfsense_plugin_cli.build_targets import this_platform
from surfsense_plugin_cli.packaging.install_requirements import (
    DependenciesNotInstalled,
    install_requirements,
)

# In site-packages: the sha256 of the requirements.txt it was installed from.
INSTALLED_FROM = ".installed-from"


def install_dependencies(plugin: Path) -> None:
    """Into plugins/<id>/site-packages, where the SDK looks, for this machine."""
    requirements = plugin / "requirements.txt"
    if not requirements.is_file():
        return
    site_packages = plugin / "site-packages"
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    stamp = site_packages / INSTALLED_FROM
    if stamp.is_file() and stamp.read_text() == digest:
        return

    # Built aside and swapped in whole, so a failed install leaves the last good one.
    staging = Path(tempfile.mkdtemp(prefix="surfsense-site-packages-"))
    platform = this_platform()
    typer.echo(f"Installing dependencies for {platform}…", err=True)
    try:
        install_requirements(requirements, platform, staging)
    except DependenciesNotInstalled as refused:
        shutil.rmtree(staging, ignore_errors=True)
        typer.echo(str(refused), err=True)
        raise typer.Exit(1) from None
    (staging / INSTALLED_FROM).write_text(digest)
    shutil.rmtree(site_packages, ignore_errors=True)
    shutil.move(staging, site_packages)
