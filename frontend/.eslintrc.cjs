module.exports = {
  root: true,
  env: { browser: true, es2020: true },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react-hooks/recommended',
  ],
  ignorePatterns: ['dist', '.eslintrc.cjs'],
  parser: '@typescript-eslint/parser',
  plugins: ['react-refresh'],
  rules: {
    // Allow components exported alongside hooks/utilities
    'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
    // Allow index signatures for lookup objects (e.g. Record<string, ...>)
    '@typescript-eslint/no-explicit-any': 'off',
    // Allow unused vars prefixed with _ (common pattern for intentional ignores)
    '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
  },
}
