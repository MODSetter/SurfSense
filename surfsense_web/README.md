# Next.js Token Handler Component

This project includes a reusable client component for Next.js that handles token storage from URL parameters.

## TokenHandler Component

The `TokenHandler` component is designed to:

1. Extract a token from URL parameters
2. Store the token in localStorage
3. Redirect the user to a specified path

### Usage

```tsx
import TokenHandler from '@/components/TokenHandler';

export default function AuthCallbackPage() {
  return (
    <div>
      <h1>Authentication Callback</h1>
      <TokenHandler 
        redirectPath="/dashboard" 
        tokenParamName="token" 
        storageKey="auth_token" 
      />
    </div>
  );
}
```

### Props

The component accepts the following props:

- `redirectPath` (optional): Path to redirect after storing token (default: '/')
- `tokenParamName` (optional): Name of the URL parameter containing the token (default: 'token')
- `storageKey` (optional): Key to use when storing in localStorage (default: 'auth_token')

### Example URL

After authentication, redirect users to:
```
https://your-domain.com/auth/callback?token=your-auth-token
```

## Implementation Details

- Uses Next.js's `useSearchParams` hook to access URL parameters
- Uses `useRouter` for client-side navigation after token storage
- Includes error handling for localStorage operations
- Displays a loading message while processing

## Security Considerations

- This implementation assumes the token is passed securely
- Consider using HTTPS to prevent token interception
- For enhanced security, consider using HTTP-only cookies instead of localStorage
- The token in the URL might be visible in browser history and server logs

This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
