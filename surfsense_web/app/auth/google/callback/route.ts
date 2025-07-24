import { NextRequest, NextResponse } from 'next/server';

// Extend global type for OAuth sessions
declare global {
  var oauthSessions: Map<string, {
    access_token: string;
    refresh_token: string;
    connector_name: string;
    timestamp: number;
  }> | undefined;
}

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const error = searchParams.get('error');

    // Handle OAuth errors
    if (error) {
      console.error('OAuth error:', error);
      return NextResponse.redirect(
        new URL(`/dashboard?error=${encodeURIComponent('Google authentication failed')}`, request.url)
      );
    }

    // Validate required parameters
    if (!code) {
      console.error('No authorization code received');
      return NextResponse.redirect(
        new URL(`/dashboard?error=${encodeURIComponent('No authorization code received')}`, request.url)
      );
    }

    // Parse state parameter
    let stateData;
    try {
      stateData = state ? JSON.parse(state) : {};
    } catch (e) {
      console.error('Invalid state parameter:', e);
      stateData = {};
    }

    const { connector_name, search_space_id } = stateData;

    // Exchange authorization code for tokens
    const tokenResponse = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        code,
        client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '',
        client_secret: process.env.GOOGLE_OAUTH_CLIENT_SECRET || '',
        redirect_uri: `${request.nextUrl.origin}/auth/google/callback`,
        grant_type: 'authorization_code',
      }),
    });

    if (!tokenResponse.ok) {
      const errorData = await tokenResponse.text();
      console.error('Token exchange failed:', errorData);
      return NextResponse.redirect(
        new URL(`/dashboard?error=${encodeURIComponent('Failed to exchange authorization code for tokens')}`, request.url)
      );
    }

    const tokens = await tokenResponse.json();
    const { access_token, refresh_token } = tokens;

    if (!access_token) {
      console.error('No access token received');
      return NextResponse.redirect(
        new URL(`/dashboard?error=${encodeURIComponent('No access token received')}`, request.url)
      );
    }

    // Store tokens securely in sessionStorage via a temporary session
    // Create a temporary session ID to store the tokens securely
    const sessionId = Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
    
    // In a real implementation, you'd store this in Redis or a database
    // For now, we'll use a simple in-memory store (note: this won't work in production with multiple instances)
    global.oauthSessions = global.oauthSessions || new Map();
    global.oauthSessions.set(sessionId, {
      access_token,
      refresh_token,
      connector_name: connector_name || 'Google Drive Connector',
      timestamp: Date.now()
    });

    // Clean up old sessions (older than 10 minutes)
    const tenMinutesAgo = Date.now() - 10 * 60 * 1000;
    Array.from(global.oauthSessions.entries()).forEach(([key, value]) => {
      if (value.timestamp < tenMinutesAgo) {
        global.oauthSessions!.delete(key);
      }
    });
    
    // Redirect back to the Google Drive connector page with the session ID
    const redirectUrl = search_space_id 
      ? `/dashboard/${search_space_id}/connectors/add/google-drive-connector?oauth_success=true&session=${sessionId}`
      : `/dashboard?oauth_success=true&session=${sessionId}`;

    return NextResponse.redirect(new URL(redirectUrl, request.url));

  } catch (error) {
    console.error('OAuth callback error:', error);
    return NextResponse.redirect(
      new URL(`/dashboard?error=${encodeURIComponent('OAuth callback failed')}`, request.url)
    );
  }
}