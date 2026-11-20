const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const ts = require('typescript')
const vm = require('node:vm')
const root = path.resolve(__dirname, '..')
const read = file => fs.readFileSync(path.join(root, 'src', file), 'utf8')

function load(file) {
  const source = ts.transpileModule(read(file), {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText
  const exports = {}
  vm.runInNewContext(source,{exports,require:id=>id.includes('config')?{whatsappDefaultConfig:{}}:{NOT_SUPPORTED_CAPABILITIES:{}},URL,globalThis:{}})
  return exports
}
const {whatsappPlatform,whatsappModule}=load('platforms/whatsapp/index.ts')
assert.equal(whatsappPlatform.status,'supported')
assert.equal(whatsappPlatform.automaticExecutionSupported,false,'hosted integration must never enable the local executor')
assert.equal(whatsappPlatform.integration,'hosted_web')
assert.equal(whatsappModule.implementation,'embedded')
const permissions=load('app/routePermissions.ts')
assert(permissions.canAccessPlatform(whatsappPlatform,2))
assert.deepEqual(JSON.parse(JSON.stringify(permissions.filterRoutesByPlatformAvailability([{key:'accounts'}],whatsappPlatform))),[{key:'accounts'}])
assert.equal(permissions.canAccessRoute('diagnostic',2),false,'existing technician-only desktop tools stay protected')
assert.equal(permissions.canAccessRoute('whatsapp-settings',2),true)
const shell=read('components/AppShell.tsx')
assert.match(shell,/event|WhatsAppWorkspace/)
assert.match(shell,/whatsappVisited/)
const frame=read('platforms/whatsapp/pages/WhatsAppWorkspace.tsx')
assert.match(frame,/event.source !== frame.current\?\.contentWindow/)
assert.match(frame,/sameOrigin\(event.origin, baseUrl\)/)
assert.doesNotMatch(frame,/accessToken|refreshToken|password:/,'desktop credentials must never cross the bridge')
console.log('WhatsApp hosted workspace, role boundaries and local-executor isolation passed')
