export const cacheKeys = {
  documents: 0,
  chats: 0,
  searchspaces: 0,
  user: 0,
  connectors: 0,
  llmconfigs: 0,
  config: 0
};

const ENDPOINTS_CONFIG = {
  'users/me': false,
  'api/v1/chats': true,
  'api/v1/documents': true,
  'api/v1/searchspaces': true,
  'api/v1/search-source-connectors': false,
  'api/v1/llm-configs': true,
  'api/v1/search-spaces': false
};

function isDetailEndpoint(url: string): boolean {
  return /\/\d+$/.test(url) || /\/[a-f0-9-]{8,}$/.test(url);
}

function formatUrlPath(url: string): string {
  let basePath = url;
  let queryParams = '';
  
  if (url.includes('?')) {
    [basePath, queryParams] = url.split('?');
    queryParams = `?${queryParams}`;
  }

  if (isDetailEndpoint(basePath)) {
    if (basePath.endsWith('/')) {
      basePath = basePath.slice(0, -1);
    }
    return basePath + queryParams;
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
 * API client with Next.js caching, URL handling, and cache invalidation
 */
export async function fetchWithCache(url: string, options: RequestInit & {
  revalidate?: number | false,
  tag?: keyof typeof cacheKeys
} = {}) {
  const { revalidate, tag, ...fetchOptions } = options;

  let formattedUrl = formatUrlPath(url);
  
  if (tag) {
    const separator = formattedUrl.includes('?') ? '&' : '?';
    formattedUrl += `${separator}v=${cacheKeys[tag]}`;
  }

  if (formattedUrl.includes('documents') && formattedUrl.includes('page_size=')) {
    const separator = formattedUrl.includes('?') ? '&' : '?';
    formattedUrl += `${separator}t=${Date.now()}`;
  }

  const headers = new Headers(fetchOptions.headers || {});
  headers.set('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');
  headers.set('Pragma', 'no-cache');
  headers.set('Expires', '0');

  const response = await fetch(formattedUrl, {
    ...fetchOptions,
    headers,
    cache: 'force-cache', // Next.js internal cache still works
    next: revalidate !== undefined ? { revalidate } : undefined,
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  
  return response.json();
}

export function invalidateCache(tag: keyof typeof cacheKeys) {
  cacheKeys[tag]++;
}