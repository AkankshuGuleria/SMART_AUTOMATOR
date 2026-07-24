import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/**
 * Vitest configuration — AUTOMATA frontend testing (SKILLS.md §3)
 *
 * Run tests:        npm test
 * Watch mode:       npm run test:watch
 * Coverage report:  npm run test:coverage
 */
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    // Use jsdom to simulate a browser environment for React component tests
    environment: 'jsdom',

    // Auto-import @testing-library/jest-dom matchers (toBeInTheDocument, etc.)
    setupFiles: ['./src/test/setup.ts'],

    // Coverage config (SKILLS.md §1 — track what's tested)
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/test/**',
        'src/**/*.d.ts',
        'src/main.tsx',         // entry point, not unit-testable
      ],
      // Start low, raise as tests are written (Phase 2: 60%, Phase 4: 80%)
      thresholds: {
        statements: 0,
        branches: 0,
        functions: 0,
        lines: 0,
      },
    },

    // Include .tsx/.ts test files
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    globals: true,
  },

  // Preserve dev server config from original vite.config.ts
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
