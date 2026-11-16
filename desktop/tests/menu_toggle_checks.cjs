const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const appShell = fs.readFileSync(
  path.resolve(__dirname, '../src/components/AppShell.tsx'),
  'utf8',
)

assert.match(appShell, /openKeys=\{openKeys\}/, 'menu must keep controlled open keys')
assert.match(appShell, /onOpenChange=\{setOpenKeys\}/, 'menu must accept Ant Design toggle state')
assert.match(appShell, /onTitleClick: route\.menuGroup\.key === 'publishing'/, 'publishing group keeps first-click navigation')
assert.doesNotMatch(
  appShell,
  /queueMicrotask\(.*publishing/s,
  'publishing group must not be force-opened after Ant Design toggles it closed',
)

console.log('menu toggle checks PASS')
