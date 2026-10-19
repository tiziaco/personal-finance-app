/** Analytics are costlier than a list; any transaction write invalidates them sooner (use-invalidate-transactions). */
export const ANALYTICS_STALE_TIME = 2 * 60 * 1000
