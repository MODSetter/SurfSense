/**
 * Environment-aware logger utility for SurfSense browser extension.
 * 
 * In development mode: Uses console.log for debugging
 * In production mode: Suppresses debug logs, only shows warnings and errors
 * 
 * Usage:
 *   import { logger } from '~/lib/logger';
 *   logger.debug('Debug message', data);
 *   logger.info('Info message');
 *   logger.warn('Warning message');
 *   logger.error('Error message', error);
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LoggerConfig {
  isDevelopment: boolean;
  prefix: string;
}

const config: LoggerConfig = {
  // Plasmo sets NODE_ENV during build
  isDevelopment: process.env.NODE_ENV !== 'production',
  prefix: '[SurfSense]',
};

const formatMessage = (level: LogLevel, message: string): string => {
  const timestamp = new Date().toISOString();
  return `${config.prefix} [${timestamp}] [${level.toUpperCase()}] ${message}`;
};

export const logger = {
  /**
   * Debug level logging - only shows in development
   */
  debug: (message: string, ...args: unknown[]): void => {
    if (config.isDevelopment) {
      console.log(formatMessage('debug', message), ...args);
    }
  },

  /**
   * Info level logging - only shows in development
   */
  info: (message: string, ...args: unknown[]): void => {
    if (config.isDevelopment) {
      console.info(formatMessage('info', message), ...args);
    }
  },

  /**
   * Warning level logging - always shows
   */
  warn: (message: string, ...args: unknown[]): void => {
    console.warn(formatMessage('warn', message), ...args);
  },

  /**
   * Error level logging - always shows
   */
  error: (message: string, ...args: unknown[]): void => {
    console.error(formatMessage('error', message), ...args);
  },

  /**
   * Check if we're in development mode
   */
  isDev: (): boolean => config.isDevelopment,
};

export default logger;
