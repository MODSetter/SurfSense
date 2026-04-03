import { execSync } from 'child_process';
import { systemPreferences } from 'electron';

export function getFrontmostApp(): string {
  try {
    if (process.platform === 'darwin') {
      return execSync(
        'osascript -e \'tell application "System Events" to get name of first application process whose frontmost is true\''
      ).toString().trim();
    }
    if (process.platform === 'win32') {
      return execSync(
        'powershell -command "Add-Type \'using System; using System.Runtime.InteropServices; public class W { [DllImport(\\\"user32.dll\\\")] public static extern IntPtr GetForegroundWindow(); }\'; (Get-Process | Where-Object { $_.MainWindowHandle -eq [W]::GetForegroundWindow() }).ProcessName"'
      ).toString().trim();
    }
  } catch {
    return '';
  }
  return '';
}

export function simulatePaste(): void {
  if (process.platform === 'darwin') {
    execSync('osascript -e \'tell application "System Events" to keystroke "v" using command down\'');
  } else if (process.platform === 'win32') {
    execSync('powershell -command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait(\'^v\')"');
  }
}

export function checkAccessibilityPermission(): boolean {
  if (process.platform !== 'darwin') return true;
  return systemPreferences.isTrustedAccessibilityClient(true);
}

export function hasAccessibilityPermission(): boolean {
  if (process.platform !== 'darwin') return true;
  return systemPreferences.isTrustedAccessibilityClient(false);
}
