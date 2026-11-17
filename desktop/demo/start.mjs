import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
import { createServer } from 'vite'

const root = fileURLToPath(new URL('..', import.meta.url))
const sectorRoot = process.env.SECTOR_ROOT || resolve(root, '../../h-sector')
const authority = spawn(process.execPath, ['--import', 'tsx', resolve(sectorRoot, 'demo/whatsapp-sso-server.ts')], { cwd: sectorRoot, stdio: ['ignore', 'inherit', 'inherit', 'ipc'] })
const backend = spawn(process.execPath, [fileURLToPath(new URL('./whatsapp-server.cjs', import.meta.url))], { stdio: 'inherit' })
const server = await createServer({ root, mode: 'demo', server: { host: '127.0.0.1', port: 1420, strictPort: true } })
await server.listen()
console.log('Account Matrix demo: http://127.0.0.1:1420/demo.html')
const shutdown = async () => { backend.kill(); authority.kill(); await server.close(); process.exit() }
process.on('SIGINT', shutdown)
process.on('SIGTERM', shutdown)
backend.once('exit', () => void shutdown())
authority.once('exit', () => void shutdown())
