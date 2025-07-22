import React, { useState } from 'react';
import { useRouter } from 'next/router';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';

export default function AddGoogleCalendarConnector() {
  const [oauthCredentials, setOauthCredentials] = useState('');
  const [calendarId, setCalendarId] = useState('');
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/connectors', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          connector_type: 'GOOGLE_CALENDAR_CONNECTOR',
          config: {
            OAUTH_CREDENTIALS: oauthCredentials,
            CALENDAR_ID: calendarId,
          },
        }),
      });
      if (!res.ok) throw new Error('Failed to add connector');
      router.push('../');
    } catch (err) {
      alert('Error adding connector: ' + err.message);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h2>Add Google Calendar Connector</h2>
      <label>OAuth Credentials (JSON)</label>
      <Input
        value={oauthCredentials}
        onChange={e => setOauthCredentials(e.target.value)}
        placeholder="Paste your OAuth credentials JSON here"
        required
      />
      <label>Calendar ID</label>
      <Input
        value={calendarId}
        onChange={e => setCalendarId(e.target.value)}
        placeholder="Enter your Google Calendar ID"
        required
      />
      <Button type="submit">Add Connector</Button>
    </form>
  );
} 