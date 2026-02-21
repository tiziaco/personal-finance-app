/**
 * Environment detection helpers.
 *
 * Safe to import in both client and server components.
 * These helpers only use NODE_ENV which is available everywhere.
 */

const nodeEnv = process.env.NODE_ENV || 'development'

export const isDevelopment = nodeEnv === 'development'
export const isProduction = nodeEnv === 'production'
export const isTest = nodeEnv === 'test'
