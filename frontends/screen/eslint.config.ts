import tseslint from 'typescript-eslint'
import skipFormatting from 'eslint-config-prettier/flat'

// Flat-config migration of the former .eslintrc.json: kept the exact same
// rule set (just the localStorage restriction) rather than opting into
// typescript-eslint's recommended rules, which were never active under the
// old config either (the plugin was registered but no ruleset was applied).
export default tseslint.config(
  {
    ignores: ['node_modules/**', 'dist/**', 'build/**', '../../static/js-build/**'],
  },
  {
    files: ['**/*.ts', '**/*.d.ts'],
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        project: './tsconfig.json',
        sourceType: 'module',
      },
    },
    plugins: {
      '@typescript-eslint': tseslint.plugin,
    },
    rules: {
      // The screen client is any-free: socket payloads, window globals and
      // the Socket.IO client are typed in ts/screen/types.ts / globals.d.ts.
      // Use `unknown` and narrow where a shape really isn't known.
      '@typescript-eslint/no-explicit-any': 'error',
      'no-restricted-syntax': [
        'error',
        {
          selector: "MemberExpression[object.name='localStorage']",
          message:
            'Direct access to localStorage is disallowed. Use the safe storage helpers in ts/common/storage.ts (get/set/remove) instead.',
        },
      ],
    },
  },
  {
    files: ['ts/screen/storage.ts'],
    rules: {
      'no-restricted-syntax': 'off',
    },
  },
  skipFormatting,
)
