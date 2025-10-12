/**
 * List of API endpoints that require specific trailing slash handling
 */
const ENDPOINTS_CONFIG = {
  'users/me': false,
  'api/v1/chats': false,
  'api/v1/documents': true,
  'api/v1/searchspaces': true
};


function formatUrlPath(url: string): string {
  let basePath = url;
  let queryParams = '';
  
  if (url.includes('?')) {
    [basePath, queryParams] = url.split('?');
    queryParams = `?${queryParams}`;
  }

  let needsTrailingSlash = true;
  
  for (const [endpoint, shouldHaveSlash] of Object.entries(ENDPOINTS_CONFIG)) {
    if (basePath.includes(endpoint)) {
      needsTrailingSlash = shouldHaveSlash;
      break;
    }
  }

  if (needsTrailingSlash && !basePath.endsWith('/')) {
    basePath = `${basePath}/`;
  } else if (!needsTrailingSlash && basePath.endsWith('/')) {
    basePath = basePath.slice(0, -1);
  }

  return basePath + queryParams;
}

/**
 * API client with Next.js caching and careful URL handling
 */
export async function fetchWithCache(url: string, options: RequestInit & {
  revalidate?: number | false,
} = {}) {
  const { revalidate, ...fetchOptions } = options;

  const formattedUrl = formatUrlPath(url);

  const response = await fetch(formattedUrl, {
    ...fetchOptions,
    cache: 'force-cache',
    next: revalidate !== undefined ? { revalidate } : undefined,
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  
  return response.json();
}