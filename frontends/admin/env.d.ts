/// <reference types="vite/client" />

declare const __GIT_COMMIT__: string

// `Intl.supportedValuesOf` is ES2022 (widely supported in browsers, but
// ahead of this project's configured `lib`) — declared here rather than
// bumping the lib target for one method.
declare namespace Intl {
  function supportedValuesOf(key: string): string[]
}
