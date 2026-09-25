// Makes jest-dom's matchers visible to tsc in this package. vitest.setup.ts
// registers them at runtime but belongs to no tsconfig, so its type
// augmentation does not reach here.
import "@testing-library/jest-dom/vitest"
