/**
 * src/test/setup.ts — Vitest global test setup (SKILLS.md §3)
 *
 * Imports @testing-library/jest-dom to add custom matchers:
 *   toBeInTheDocument(), toHaveClass(), toBeDisabled(), etc.
 *
 * This file is referenced in vite.config.ts → test.setupFiles.
 */
import '@testing-library/jest-dom'

Element.prototype.scrollIntoView = () => {}
