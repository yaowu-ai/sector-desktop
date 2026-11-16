const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')
const filename = path.resolve(__dirname, '../src/services/refreshQueue.ts')
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText
const moduleObject = { exports: {} }
vm.runInNewContext(compiled, { module: moduleObject, exports: moduleObject.exports, Promise })
const { createRefreshQueue } = moduleObject.exports

async function main() {
  const refresh = createRefreshQueue()
  const events = []
  let finish
  const first = refresh(async () => { events.push('first'); await new Promise(resolve => { finish = resolve }) })
  const second = refresh(async () => { events.push('obsolete') })
  const third = refresh(async () => { events.push('latest') })
  assert.deepEqual(events, ['first'])
  finish()
  await Promise.all([first, second, third])
  assert.deepEqual(events, ['first', 'latest'])
  await assert.rejects(refresh(async () => { throw new Error('failed') }), /failed/)
  await refresh(async () => { events.push('recovered') })
  assert.equal(events.at(-1), 'recovered')
  console.log('refresh queue: serial execution, latest refresh and error recovery passed')
}
main().catch(error => { console.error(error); process.exitCode = 1 })
