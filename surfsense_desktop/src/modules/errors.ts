import { app, clipboard, dialog } from 'electron';

export function showErrorDialog(title: string, error: unknown): void {
  const err = error instanceof Error ? error : new Error(String(error));
  console.error(`${title}:`, err);

  if (app.isReady()) {
    const detail = err.stack || err.message;
    const buttonIndex = dialog.showMessageBoxSync({
      type: 'error',
      buttons: ['OK', process.platform === 'darwin' ? 'Copy Error' : 'Copy error'],
      defaultId: 0,
      noLink: true,
      message: title,
      detail,
    });
    if (buttonIndex === 1) {
      clipboard.writeText(`${title}\n${detail}`);
    }
  } else {
    dialog.showErrorBox(title, err.stack || err.message);
  }
}

export function registerGlobalErrorHandlers(): void {
  process.on('uncaughtException', (error) => {
    showErrorDialog('Unhandled Error', error);
  });

  process.on('unhandledRejection', (reason) => {
    showErrorDialog('Unhandled Promise Rejection', reason);
  });
}
