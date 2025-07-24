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
    const sessionId = searchParams.get('session');

    if (!sessionId) {
      return NextResponse.json({ error: 'Session ID required' }, { status: 400 });
    }

    // Retrieve session from temporary store
    const sessions = global.oauthSessions || new Map();
    const sessionData = sessions.get(sessionId);

    if (!sessionData) {
      return NextResponse.json({ error: 'Session not found or expired' }, { status: 404 });
    }

    // Remove the session after use for security
    sessions.delete(sessionId);

    return NextResponse.json({
      access_token: sessionData.access_token,
      refresh_token: sessionData.refresh_token,
      connector_name: sessionData.connector_name
    });

  } catch (error) {
    console.error('Error retrieving OAuth session:', error);
    return NextResponse.json({ error: 'Failed to retrieve session' }, { status: 500 });
  }
}