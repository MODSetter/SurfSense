import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    const authHeader = request.headers.get('authorization');
    
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return NextResponse.json({ error: 'Authorization header required' }, { status: 401 });
    }

    const accessToken = authHeader.substring(7); // Remove 'Bearer ' prefix

    // Fetch user's Google Drive files
    const filesResponse = await fetch('https://www.googleapis.com/drive/v3/files?pageSize=100&fields=files(id,name,mimeType,size,modifiedTime,webViewLink,parents)', {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
      },
    });

    if (!filesResponse.ok) {
      const errorData = await filesResponse.text();
      console.error('Google Drive API error:', errorData);
      return NextResponse.json({ 
        error: 'Failed to fetch Google Drive files',
        details: errorData 
      }, { status: filesResponse.status });
    }

    const filesData = await filesResponse.json();
    
    return NextResponse.json({
      files: filesData.files || []
    });

  } catch (error) {
    console.error('Error fetching Google Drive files:', error);
    return NextResponse.json({ error: 'Failed to fetch files' }, { status: 500 });
  }
}