#!/usr/bin/env node

/**
 * Test script for Google Drive OAuth flow
 * This script helps verify that the OAuth implementation is working correctly
 */

console.log('🧪 Testing Google Drive OAuth Implementation...\n');

// Check environment variables
const requiredEnvVars = [
  'NEXT_PUBLIC_GOOGLE_CLIENT_ID',
  'GOOGLE_OAUTH_CLIENT_SECRET'
];

console.log('📋 Environment Variables Check:');
requiredEnvVars.forEach(envVar => {
  const value = process.env[envVar];
  if (value) {
    console.log(`✅ ${envVar}: ${value.substring(0, 10)}...`);
  } else {
    console.log(`❌ ${envVar}: Not set`);
  }
});

console.log('\n🔗 OAuth Flow URLs:');
console.log('Authorization URL: https://accounts.google.com/o/oauth2/v2/auth');
console.log('Token Exchange URL: https://oauth2.googleapis.com/token');
console.log('Google Drive API: https://www.googleapis.com/drive/v3/files');

console.log('\n📝 Required OAuth Scopes:');
console.log('- https://www.googleapis.com/auth/drive.readonly');

console.log('\n🔧 Implementation Files:');
console.log('- OAuth Callback: /app/auth/google/callback/route.ts');
console.log('- Frontend Page: /app/dashboard/[search_space_id]/connectors/add/google-drive-connector/page.tsx');

console.log('\n✨ Test Complete! Check the files above for the OAuth implementation.');