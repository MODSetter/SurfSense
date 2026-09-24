import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
  },
  {
    files: ['src/components/ui/**'],
    rules: { 'react-refresh/only-export-components': 'off' },
  },
  {
    // The compiled catalogs are an implementation detail of src/i18n/intl.ts.
    files: ['src/**/*.{ts,tsx}'],
    ignores: ['src/i18n/**'],
    rules: {
      'no-restricted-imports': [
        'error',
        { patterns: ['**/i18n/compiled/*', '**/translations/*.json'] },
      ],
    },
  },
])
