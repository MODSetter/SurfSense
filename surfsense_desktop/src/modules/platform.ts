import { execSync } from 'child_process';
import { systemPreferences } from 'electron';

const EXEC_OPTS = { windowsHide: true } as const;

export function getFrontmostApp(): string {
  try {
    if (process.platform === 'darwin') {
      return execSync(
        'osascript -e \'tell application "System Events" to get name of first application process whose frontmost is true\'',
        EXEC_OPTS,
      ).toString().trim();
    }
    if (process.platform === 'win32') {
      return execSync(
        'powershell -NoProfile -NonInteractive -command "Add-Type \'using System; using System.Runtime.InteropServices; public class W { [DllImport(\\\"user32.dll\\\")] public static extern IntPtr GetForegroundWindow(); }\'; (Get-Process | Where-Object { $_.MainWindowHandle -eq [W]::GetForegroundWindow() }).ProcessName"',
        EXEC_OPTS,
      ).toString().trim();
    }
  } catch {
    return '';
  }
  return '';
}

export function simulatePaste(): void {
  if (process.platform === 'darwin') {
    execSync('osascript -e \'tell application "System Events" to keystroke "v" using command down\'', EXEC_OPTS);
  } else if (process.platform === 'win32') {
    execSync('powershell -NoProfile -NonInteractive -command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait(\'^v\')"', EXEC_OPTS);
  }
}

export function simulateCopy(): boolean {
  try {
    if (process.platform === 'darwin') {
      execSync('osascript -e \'tell application "System Events" to keystroke "c" using command down\'', EXEC_OPTS);
    } else if (process.platform === 'win32') {
      execSync('powershell -NoProfile -NonInteractive -command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait(\'^c\')"', EXEC_OPTS);
    }
    return true;
  } catch (err) {
    console.error('[simulateCopy] Failed:', err);
    return false;
  }
}

export function checkAccessibilityPermission(): boolean {
  if (process.platform !== 'darwin') return true;
  return systemPreferences.isTrustedAccessibilityClient(true);
}

export function getWindowTitle(): string {
  try {
    if (process.platform === 'darwin') {
      return execSync(
        'osascript -e \'tell application "System Events" to get title of front window of first application process whose frontmost is true\'',
        EXEC_OPTS,
      ).toString().trim();
    }
    if (process.platform === 'win32') {
      return execSync(
        'powershell -NoProfile -NonInteractive -command "(Get-Process | Where-Object { $_.MainWindowHandle -eq (Add-Type -MemberDefinition \'[DllImport(\\\"user32.dll\\\")] public static extern IntPtr GetForegroundWindow();\' -Name W -PassThru)::GetForegroundWindow() }).MainWindowTitle"',
        EXEC_OPTS,
      ).toString().trim();
    }
  } catch {
    return '';
  }
  return '';
}

export function hasAccessibilityPermission(): boolean {
  if (process.platform !== 'darwin') return true;
  return systemPreferences.isTrustedAccessibilityClient(false);
}
