import { defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      coverage: {
        provider: 'v8',
        // Whole source tree, so files no test imports show up as 0 %.
        include: ['ts/**/*.ts'],
        exclude: ['ts/**/*.test.ts', 'ts/**/*.d.ts'],
        reporter: ['text', 'json-summary'],
      },
    },
  }),
)
