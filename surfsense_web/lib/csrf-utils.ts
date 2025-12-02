/**
 * CSRF Token Utilities
 * Handles CSRF token management for secure requests
 */

const CSRF_COOKIE_NAME = 'csrf_token';
const CSRF_HEADER_NAME = 'X-CSRF-Token';

/**
 * Get CSRF token from cookie
 * @returns CSRF token or null if not found
 */
export function getCSRFTokenFromCookie(): string | null {
  if (typeof document === 'undefined') return null;
  
  const cookies = document.cookie.split(';');
  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split('=');
    if (name === CSRF_COOKIE_NAME) {
      return decodeURIComponent(value);
    }
  }
  return null;
}

/**
 * Fetch a new CSRF token from the backend
 * @returns Promise with the CSRF token
 */
export async function fetchCSRFToken(): Promise<string> {
  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/csrf/token`,
      {
        method: 'GET',
        credentials: 'include', // Important: include cookies
      }
    );
    
    if (!response.ok) {
      throw new Error('Failed to fetch CSRF token');
    }
    
    const data = await response.json();
    return data.csrf_token;
  } catch (error) {
    console.error('Error fetching CSRF token:', error);
    throw error;
  }
}

/**
 * Ensure CSRF token is available, fetch if not
 * @returns Promise with the CSRF token
 */
export async function ensureCSRFToken(): Promise<string> {
  // First check if token exists in cookie
  let token = getCSRFTokenFromCookie();
  
  // If not, fetch a new one
  if (!token) {
    token = await fetchCSRFToken();
  }
  
  return token;
}

/**
 * Get CSRF header name
 * @returns CSRF header name
 */
export function getCSRFHeaderName(): string {
  return CSRF_HEADER_NAME;
}
