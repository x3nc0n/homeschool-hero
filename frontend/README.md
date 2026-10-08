# React + TypeScript + Vite

## Curriculum import

The curriculum wizard never saves during analysis. AI document/URL uploads create
`POST /api/curriculum/ai-import-sessions` sessions and poll their GET endpoint every
two seconds while processing. Ready drafts remain editable; failed/expired sessions
stop polling and require an explicit new analysis. Closing or unmounting the wizard
cancels unconfirmed sessions with DELETE, including uploads that finish after closing.
Copy edited JSON before restarting an expired session. No cloud-provider fallback is
performed by the client.

Both AI and manual JSON drafts are checked through
`POST /api/curriculum/import/duplicate-check` after edits. Confirmation is blocked
until the current draft is checked and every current duplicate is acknowledged.
Acknowledgement imports a separate curriculum; it never merges or drops lessons.
Name conflicts still require renaming. `metadata.edition` is an optional string.
Unknown fields are preserved in the editable JSON sent to confirmation.

AI confirmation posts `{draft, client_revision, acknowledged_duplicate_ids}` to
the session's `/confirm` endpoint; manual confirmation posts
`{draft, acknowledged_duplicate_ids}` to `/api/curriculum/import/confirm`.
Structured 409 duplicate responses return the user to review with edits intact.
Legacy API helpers remain available for compatibility.

Development-only mock fallback supports the same processing/ready/expired session,
cancellation, revision, duplicate-check and separate-confirmation behavior. Its AI
draft is explicitly marked as sample data. Production never falls back to this mock.
Run `npm run test:curriculum-import` for regression coverage, or `npm test` for all
frontend tests; `npm run lint` and `npm run build` validate the UI and types.

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```
