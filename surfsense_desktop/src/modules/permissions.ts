import { app } from 'electron';

type PermissionStatus = 'authorized' | 'denied' | 'not determined' | 'restricted' | 'limited';

export interface PermissionsStatus {
  accessibility: PermissionStatus;
}

function isMac(): boolean {
  return process.platform === 'darwin';
}

function getNodeMacPermissions() {
  return require('node-mac-permissions');
}

export function getPermissionsStatus(): PermissionsStatus {
  if (!isMac()) {
    return { accessibility: 'authorized' };
  }

  const perms = getNodeMacPermissions();
  return {
    accessibility: perms.getAuthStatus('accessibility'),
  };
}

export function allPermissionsGranted(): boolean {
  const status = getPermissionsStatus();
  return status.accessibility === 'authorized';
}

export function requestAccessibility(): void {
  if (!isMac()) return;
  const perms = getNodeMacPermissions();
  perms.askForAccessibilityAccess();
}

export function restartApp(): void {
  app.relaunch();
  app.exit(0);
}
