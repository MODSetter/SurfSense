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
      // enforce-placeholders reads values only from an object literal, so a
      // variable or a spread would pass with a placeholder unfilled.
      'no-restricted-syntax': [
        'error',
        {
          selector:
            "CallExpression[callee.property.name='formatMessage'][arguments.1][arguments.1.type!='ObjectExpression']",
          message:
            'Pass formatMessage its values as an object literal, so enforce-placeholders can check them.',
        },
        {
          selector:
            "CallExpression[callee.property.name='formatMessage'] > ObjectExpression > SpreadElement",
          message:
            'Write each formatMessage value out in the literal; a spread hides it from enforce-placeholders.',
        },
        // Buttons share one look and one press motion, from components/ui/button.tsx.
        {
          selector: "JSXOpeningElement[name.name='button']",
          message:
            'Use Button from @/components/ui/button; variant="bare" for an element with its own layout.',
        },
        {
          selector:
            "JSXOpeningElement[name.name='Button'] JSXAttribute[name.name='className'] Literal[value=/active:\\S*(scale|translate)/]",
          message:
            'Press motion comes from Button itself; pass static to turn it off.',
        },
        // The highlighter ships only the themes it names (code-highlighter.ts).
        {
          selector: "JSXAttribute[name.name='shikiTheme']",
          message:
            "Streamdown takes code themes from getThemes() in code-highlighter.ts and chat replies from assistant-ui's DEFAULT_SHIKI_THEME; the highlighter ships only github-light and github-dark, so add a theme to its map first.",
        },
      ],
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
