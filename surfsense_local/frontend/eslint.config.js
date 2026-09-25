import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import formatjs from 'eslint-plugin-formatjs'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist', 'src/i18n/compiled']),
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
    // Interface text: every call carries its English for `formatjs extract`,
    // passes every placeholder, and uses a <feature>_<surface>_<purpose> id.
    files: ['src/**/*.{ts,tsx}'],
    ignores: ['src/**/*.test.{ts,tsx}'],
    plugins: { formatjs },
    rules: {
      'formatjs/enforce-default-message': ['error', 'literal'],
      'formatjs/enforce-placeholders': 'error',
      'formatjs/enforce-id': [
        'error',
        {
          idInterpolationPattern: '[sha512:contenthash:base64:6]',
          idWhitelist: [
            '^[a-z0-9]+_([a-z0-9]+_)*(title|body|label|placeholder|button|tooltip|empty|error|toast|aria|link|status)$',
            '^[a-z0-9]+_error_[a-z0-9_]+$',
          ],
        },
      ],
    },
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
