import { app } from 'electron';

type PermissionStatus = 'authorized' | 'denied' | 'not determined' | 'restricted' | 'limited';

export interface PermissionsStatus {
  accessibility: PermissionStatus;
  screenRecording: PermissionStatus;
}

function isMac(): boolean {
  return process.platform === 'darwin';
}

function getNodeMacPermissions() {
  return require('node-mac-permissions');
}

export function getPermissionsStatus(): PermissionsStatus {
  if (!isMac()) {
    return { accessibility: 'authorized', screenRecording: 'authorized' };
  }

  const perms = getNodeMacPermissions();
  return {
    accessibility: perms.getAuthStatus('accessibility'),
    screenRecording: perms.getAuthStatus('screen'),
  };
}

export function allPermissionsGranted(): boolean {
  const status = getPermissionsStatus();
  return status.accessibility === 'authorized' && status.screenRecording === 'authorized';
}

export function requestAccessibility(): void {
  if (!isMac()) return;
  const perms = getNodeMacPermissions();
  perms.askForAccessibilityAccess();
}

export function hasScreenRecordingPermission(): boolean {
  if (!isMac()) return true;
  const perms = getNodeMacPermissions();
  return perms.getAuthStatus('screen') === 'authorized';
}

export function requestScreenRecording(): void {
  if (!isMac()) return;
  const perms = getNodeMacPermissions();
  perms.askForScreenCaptureAccess();
}

export function restartApp(): void {
  app.relaunch();
  app.exit(0);
}
