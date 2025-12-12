/**
 * Simple in-memory cache with TTL (Time To Live) support
 * Reduces API calls for frequently accessed data
 */

const cache = new Map();

/**
 * Default TTL values in milliseconds
 */
export const CACHE_TTL = {
  STATS: 5 * 60 * 1000,        // 5 minutes for stats
  METRICS: 10 * 60 * 1000,     // 10 minutes for metrics data
  SESSIONS: 10 * 60 * 1000,    // 10 minutes for sessions data
  DRAFT: 30 * 1000,            // 30 seconds for draft (needs to be fresh)
};

/**
 * Get data from cache if valid
 * @param {string} key - Cache key
 * @returns {any|null} - Cached data or null if expired/missing
 */
export const getFromCache = (key) => {
  const entry = cache.get(key);

  if (!entry) {
    return null;
  }

  const now = Date.now();
  const isExpired = now - entry.timestamp > entry.ttl;

  if (isExpired) {
    cache.delete(key);
    return null;
  }

  return entry.data;
};

/**
 * Store data in cache
 * @param {string} key - Cache key
 * @param {any} data - Data to cache
 * @param {number} ttl - Time to live in milliseconds
 */
export const setInCache = (key, data, ttl = CACHE_TTL.STATS) => {
  cache.set(key, {
    data,
    timestamp: Date.now(),
    ttl,
  });
};

/**
 * Invalidate a specific cache entry
 * @param {string} key - Cache key to invalidate
 */
export const invalidateCache = (key) => {
  cache.delete(key);
};

/**
 * Invalidate all cache entries matching a prefix
 * @param {string} prefix - Key prefix to match
 */
export const invalidateCacheByPrefix = (prefix) => {
  for (const key of cache.keys()) {
    if (key.startsWith(prefix)) {
      cache.delete(key);
    }
  }
};

/**
 * Clear entire cache
 */
export const clearCache = () => {
  cache.clear();
};

/**
 * Generate cache key for metrics range
 * @param {string} startDate
 * @param {string} endDate
 * @returns {string}
 */
export const getMetricsCacheKey = (startDate, endDate) => {
  return `metrics:${startDate}:${endDate}`;
};

/**
 * Generate cache key for sessions range
 * @param {string} startDate
 * @param {string} endDate
 * @returns {string}
 */
export const getSessionsCacheKey = (startDate, endDate) => {
  return `sessions:${startDate}:${endDate}`;
};

/**
 * Cache wrapper for async functions
 * @param {string} key - Cache key
 * @param {Function} fetchFn - Async function to call if cache miss
 * @param {number} ttl - Time to live in milliseconds
 * @returns {Promise<any>}
 */
export const withCache = async (key, fetchFn, ttl = CACHE_TTL.STATS) => {
  const cached = getFromCache(key);
  if (cached !== null) {
    return cached;
  }

  const data = await fetchFn();
  setInCache(key, data, ttl);

  return data;
};

export default {
  getFromCache,
  setInCache,
  invalidateCache,
  invalidateCacheByPrefix,
  clearCache,
  getMetricsCacheKey,
  getSessionsCacheKey,
  withCache,
  CACHE_TTL,
};
