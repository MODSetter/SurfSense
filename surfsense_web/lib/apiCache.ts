const NO_TRAILING_SLASH_ENDPOINTS = [
  'users/me',
  'api/v1/chats',
  'api/v1/search-spaces'
];

function shouldSkipTrailingSlash(url: string): boolean {
  const basePath = url.includes('?') ? url.split('?')[0] : url;
  
  return NO_TRAILING_SLASH_ENDPOINTS.some(endpoint => 
    basePath.includes(endpoint)
  );
}

/**
 * API client with Next.js caching and trailing slash handling
 */
export async function fetchWithCache(url: string, options: RequestInit & {
    revalidate?: number | false,
  } = {}) {
  const { revalidate, ...fetchOptions } = options;

  let basePath = url;
  let queryParams = '';
  
  if (url.includes('?')) {
    [basePath, queryParams] = url.split('?');
    queryParams = `?${queryParams}`;
  }
  
  if (!shouldSkipTrailingSlash(basePath)) {
    basePath = basePath.endsWith('/') ? basePath : `${basePath}/`;
  } else {
    basePath = basePath.endsWith('/') ? basePath.slice(0, -1) : basePath;
  }
  
  const formattedUrl = basePath + queryParams;

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