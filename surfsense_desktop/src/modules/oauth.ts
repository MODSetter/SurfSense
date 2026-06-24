import { shell } from 'electron';
import crypto from 'node:crypto';
import http from 'node:http';
import { writeOAuthPage } from './oauth-page';

export interface DesktopAuthTokens {
  access_token: string;
  refresh_token: string;
}

const OAUTH_TIMEOUT_MS = 5 * 60 * 1000;
const OAUTH_CALLBACK_PATH = '/callback';

function base64Url(buffer: Buffer): string {
  return buffer.toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function randomUrlSafe(bytes = 32): string {
  return base64Url(crypto.randomBytes(bytes));
}

function sha256(value: string): string {
  return base64Url(crypto.createHash('sha256').update(value).digest());
}

function getGoogleDesktopClientId(): string {
  const clientId = (process.env.GOOGLE_DESKTOP_CLIENT_ID || '').trim();
  if (!clientId) {
    throw new Error('Google desktop OAuth client ID is not configured');
  }
  return clientId;
}

export async function startGoogleOAuth(backendUrl: string): Promise<DesktopAuthTokens> {
  const clientId = getGoogleDesktopClientId();
  const state = randomUrlSafe();
  const codeVerifier = randomUrlSafe(64);
  const codeChallenge = sha256(codeVerifier);

  return new Promise((resolve, reject) => {
    let settled = false;
    let port: number | null = null;
    let timeout: NodeJS.Timeout | null = null;

    const cleanup = () => {
      if (timeout) {
        clearTimeout(timeout);
        timeout = null;
      }
      if (server.listening) {
        server.close();
      }
    };

    const fail = (error: Error) => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(error);
    };

    const succeed = (tokens: DesktopAuthTokens) => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve(tokens);
    };

    const server = http.createServer(async (req, res) => {
      try {
        const url = new URL(req.url || '/', 'http://127.0.0.1');
        if (url.pathname !== OAUTH_CALLBACK_PATH) {
          writeOAuthPage(res, 404, 'Not found', 'This OAuth callback endpoint is only used by SurfSense.');
          return;
        }

        const oauthError = url.searchParams.get('error');
        if (oauthError) {
          const description = url.searchParams.get('error_description');
          writeOAuthPage(res, 400, 'Authentication failed', 'You can close this window and return to SurfSense.', 'error');
          fail(new Error(description || `Google OAuth failed: ${oauthError}`));
          return;
        }

        const code = url.searchParams.get('code');
        const returnedState = url.searchParams.get('state');
        if (!code || returnedState !== state) {
          writeOAuthPage(res, 400, 'Authentication failed', 'You can close this window and return to SurfSense.', 'error');
          fail(new Error('Invalid OAuth callback'));
          return;
        }

        if (!port) {
          writeOAuthPage(res, 500, 'Authentication failed', 'You can close this window and return to SurfSense.', 'error');
          fail(new Error('OAuth loopback server was not ready'));
          return;
        }

        const redirectUri = `http://127.0.0.1:${port}${OAUTH_CALLBACK_PATH}`;
        const response = await fetch(`${backendUrl}/auth/desktop/session`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code, code_verifier: codeVerifier, redirect_uri: redirectUri }),
        });
        if (!response.ok) {
          let detail = 'Desktop session exchange failed';
          try {
            const error = (await response.json()) as { detail?: string };
            detail = error.detail || detail;
          } catch {
            // Keep the generic exchange error if the backend did not return JSON.
          }
          writeOAuthPage(res, 401, 'Authentication failed', 'You can close this window and return to SurfSense.', 'error');
          fail(new Error(detail));
          return;
        }
        const tokens = (await response.json()) as DesktopAuthTokens;
        writeOAuthPage(res, 200, 'Authentication complete', 'You can close this window and return to SurfSense.', 'success');
        succeed(tokens);
      } catch (error) {
        fail(error instanceof Error ? error : new Error('Google OAuth failed'));
      }
    });

    server.listen(0, '127.0.0.1', () => {
      const addressInfo = server.address();
      if (!addressInfo || typeof addressInfo === 'string') {
        fail(new Error('Unable to bind loopback OAuth server'));
        return;
      }
      port = addressInfo.port;
      timeout = setTimeout(() => {
        fail(new Error('Google OAuth timed out'));
      }, OAUTH_TIMEOUT_MS);

      const redirectUri = `http://127.0.0.1:${port}${OAUTH_CALLBACK_PATH}`;
      const authUrl = new URL('https://accounts.google.com/o/oauth2/v2/auth');
      authUrl.searchParams.set('client_id', clientId);
      authUrl.searchParams.set('redirect_uri', redirectUri);
      authUrl.searchParams.set('response_type', 'code');
      authUrl.searchParams.set('scope', 'openid email profile');
      authUrl.searchParams.set('state', state);
      authUrl.searchParams.set('code_challenge', codeChallenge);
      authUrl.searchParams.set('code_challenge_method', 'S256');

      shell.openExternal(authUrl.toString()).catch((error) => {
        fail(error instanceof Error ? error : new Error('Unable to open browser for Google OAuth'));
      });
    });

    server.on('error', (error) => {
      fail(error);
    });
  });
}
