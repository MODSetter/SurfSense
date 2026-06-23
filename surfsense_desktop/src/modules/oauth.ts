import { shell } from 'electron';
import crypto from 'node:crypto';
import http from 'node:http';

export interface DesktopAuthTokens {
  access_token: string;
  refresh_token: string;
}

function base64Url(buffer: Buffer): string {
  return buffer.toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function randomUrlSafe(bytes = 32): string {
  return base64Url(crypto.randomBytes(bytes));
}

function sha256(value: string): string {
  return base64Url(crypto.createHash('sha256').update(value).digest());
}

export async function startGoogleOAuth(backendUrl: string): Promise<DesktopAuthTokens> {
  const state = randomUrlSafe();
  const codeVerifier = randomUrlSafe(64);
  const codeChallenge = sha256(codeVerifier);

  return new Promise((resolve, reject) => {
    let address: { port: number };
    const server = http.createServer(async (req, res) => {
      try {
        const url = new URL(req.url || '/', 'http://127.0.0.1');
        const code = url.searchParams.get('code');
        const returnedState = url.searchParams.get('state');
        if (!code || returnedState !== state) {
          res.writeHead(400).end('Authentication failed. You can close this window.');
          reject(new Error('Invalid OAuth callback'));
          return;
        }

        const redirectUri = `http://127.0.0.1:${address.port}/callback`;
        const response = await fetch(`${backendUrl}/auth/desktop/session`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code, code_verifier: codeVerifier, redirect_uri: redirectUri }),
        });
        if (!response.ok) {
          res.writeHead(401).end('Authentication failed. You can close this window.');
          reject(new Error('Desktop session exchange failed'));
          return;
        }
        const tokens = (await response.json()) as DesktopAuthTokens;
        res.writeHead(200, { 'content-type': 'text/html' }).end('Authentication complete. You can close this window.');
        resolve(tokens);
      } catch (error) {
        reject(error);
      } finally {
        server.close();
      }
    });

    server.listen(0, '127.0.0.1', () => {
      const addressInfo = server.address();
      if (!addressInfo || typeof addressInfo === 'string') {
        reject(new Error('Unable to bind loopback OAuth server'));
        return;
      }
      address = addressInfo;
      const redirectUri = `http://127.0.0.1:${address.port}/callback`;
      const authUrl = new URL('https://accounts.google.com/o/oauth2/v2/auth');
      authUrl.searchParams.set('client_id', process.env.GOOGLE_DESKTOP_CLIENT_ID || '');
      authUrl.searchParams.set('redirect_uri', redirectUri);
      authUrl.searchParams.set('response_type', 'code');
      authUrl.searchParams.set('scope', 'openid email profile');
      authUrl.searchParams.set('state', state);
      authUrl.searchParams.set('code_challenge', codeChallenge);
      authUrl.searchParams.set('code_challenge_method', 'S256');
      shell.openExternal(authUrl.toString());
    });
  });
}
