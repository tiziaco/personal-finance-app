// `process.env.NODE_ENV` is defined by every bundler this package could run
// under, Metro included, so it does not violate the no-renderer rule. Declared
// narrowly rather than pulling in @types/node, which would also make `fetch`
// and `setTimeout` resolve here and blunt the point of lib: ["esnext"].
declare const process: { env: { NODE_ENV?: string } }

const nodeEnv = process.env.NODE_ENV || "development"

export const isDevelopment = nodeEnv === "development"
export const isProduction = nodeEnv === "production"
export const isTest = nodeEnv === "test"
