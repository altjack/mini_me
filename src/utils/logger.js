/**
 * Secure logging utility that prevents sensitive data exposure in production
 * Only logs in development mode
 */

const isDev = import.meta.env.DEV || import.meta.env.MODE === 'development';

/**
 * Log error messages conditionally
 * @param {string} message - Error message to log
 * @param {Error|unknown} error - Error object (optional)
 */
export const logError = (message, error = null) => {
  if (isDev) {
    if (error) {
      console.error(message, error);
    } else {
      console.error(message);
    }
  }

  // In production, you could send to error tracking service like Sentry
  // if (!isDev && error) {
  //   sendToErrorTracking(message, error);
  // }
};

/**
 * Log info messages conditionally
 * @param {string} message - Info message to log
 * @param {any} data - Additional data (optional)
 */
export const logInfo = (message, data = null) => {
  if (isDev) {
    if (data) {
      console.log(message, data);
    } else {
      console.log(message);
    }
  }
};

/**
 * Log warning messages conditionally
 * @param {string} message - Warning message to log
 * @param {any} data - Additional data (optional)
 */
export const logWarn = (message, data = null) => {
  if (isDev) {
    if (data) {
      console.warn(message, data);
    } else {
      console.warn(message);
    }
  }
};

export default {
  logError,
  logInfo,
  logWarn,
};
