import { app } from 'electron';

type PermissionStatus = 'authorized' | 'denied' | 'not determined' | 'restricted' | 'limited';

export interface PermissionsStatus {
  accessibility: PermissionStatus;
  inputMonitoring: PermissionStatus;
}

function isMac(): boolean {
  return process.platform === 'darwin';
}

function getNodeMacPermissions() {
  return require('node-mac-permissions');
}

export function getPermissionsStatus(): PermissionsStatus {
  if (!isMac()) {
    return { accessibility: 'authorized', inputMonitoring: 'authorized' };
  }

  const perms = getNodeMacPermissions();
  return {
    accessibility: perms.getAuthStatus('accessibility'),
    inputMonitoring: perms.getAuthStatus('input-monitoring'),
  };
}

export function allPermissionsGranted(): boolean {
  const status = getPermissionsStatus();
  return status.accessibility === 'authorized' && status.inputMonitoring === 'authorized';
}

export function requestAccessibility(): void {
  if (!isMac()) return;
  const perms = getNodeMacPermissions();
  perms.askForAccessibilityAccess();
}

export async function requestInputMonitoring(): Promise<string> {
  if (!isMac()) return 'authorized';
  const perms = getNodeMacPermissions();
  return perms.askForInputMonitoringAccess('listen');
}

export function restartApp(): void {
  app.relaunch();
  app.exit(0);
}
