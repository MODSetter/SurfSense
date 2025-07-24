import { NextRequest, NextResponse } from 'next/server';

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

    // Fetch user's Google Drive files
    const filesResponse = await fetch('https://www.googleapis.com/drive/v3/files?pageSize=100&fields=files(id,name,mimeType,size,modifiedTime,webViewLink,parents)', {
      headers: {
        'Authorization': `Bearer ${access_token}`,
      },
    });

    if (!filesResponse.ok) {
      console.error('Failed to fetch Google Drive files');
      return NextResponse.redirect(
        new URL(`/dashboard?error=${encodeURIComponent('Failed to fetch Google Drive files')}`, request.url)
      );
    }

    const filesData = await filesResponse.json();
    const files = filesData.files || [];

    // Store the OAuth data in sessionStorage via URL parameters
    // This is a temporary solution - in production, you might want to use a more secure method
    const oauthData = {
      access_token,
      refresh_token,
      files,
      connector_name: connector_name || 'Google Drive Connector',
    };

    // Encode the data to pass it back to the frontend
    const encodedData = encodeURIComponent(JSON.stringify(oauthData));
    
    // Redirect back to the Google Drive connector page with the OAuth data
    const redirectUrl = search_space_id 
      ? `/dashboard/${search_space_id}/connectors/add/google-drive-connector?oauth_success=true&data=${encodedData}`
      : `/dashboard?oauth_success=true&data=${encodedData}`;

    return NextResponse.redirect(new URL(redirectUrl, request.url));

  } catch (error) {
    console.error('OAuth callback error:', error);
    return NextResponse.redirect(
      new URL(`/dashboard?error=${encodeURIComponent('OAuth callback failed')}`, request.url)
    );
  }
}