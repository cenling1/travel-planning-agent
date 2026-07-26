<template>
  <router-view />
</template>

<style>
/* Global reset & base styles */
:root {
  --el-color-primary: #147d64;
  --el-color-primary-light-3: #51a08c;
  --el-color-primary-light-5: #89bcae;
  --el-color-primary-light-7: #c1d9d2;
  --el-color-primary-light-8: #d9e9e4;
  --el-color-primary-light-9: #edf5f2;
  --el-color-primary-dark-2: #106550;
  --el-color-success: #23836f;
  --el-color-warning: #b7791f;
  --el-color-danger: #c74a45;
  --el-border-radius-base: 5px;
  --el-border-radius-small: 4px;
  --el-bg-color-page: #f5f7f6;
  --el-text-color-primary: #202725;
  --el-text-color-regular: #4b5652;
  --el-border-color-light: #dfe5e2;
}

*,
*::before,
*::after {
  box-sizing: border-box;
}

html, body {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
  font-size: 14px;
  color: var(--el-text-color-primary);
  background: var(--el-bg-color-page);
  letter-spacing: 0;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#app {
  height: 100%;
}

/* Scrollbar styles */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: var(--el-border-color-dark);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: var(--el-text-color-placeholder);
}

/* Utility: prevent body scroll when mobile drawer is open */
body.drawer-open {
  overflow: hidden;
}

button, input, textarea, select { font: inherit; letter-spacing: 0; }

@media (max-width: 640px) {
  .el-dialog { width: calc(100vw - 24px) !important; margin: 12vh auto 0; }
  .el-message-box { width: calc(100vw - 24px) !important; }
}
</style>
