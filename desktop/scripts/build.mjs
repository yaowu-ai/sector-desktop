import { spawnSync } from 'node:child_process'

const mode = normalizeMode(process.argv[2] || process.env.DESKTOP_BUILD_MODE || 'production')

run('corepack', ['pnpm', 'exec', 'tsc'])
run('corepack', ['pnpm', 'exec', 'vite', 'build', '--mode', mode])

function normalizeMode(value) {
  const normalized = String(value || '').trim().toLowerCase()

  if (normalized === 'test') return 'test'
  if (normalized === 'production' || normalized === 'prod' || normalized === '') return 'production'

  throw new Error(`Unsupported build mode: ${value}`)
}

function run(command, args) {
  const result = spawnSync(command, args, {
    stdio: 'inherit',
    env: process.env,
  })

  if (result.error) {
    throw result.error
  }

  if (result.status !== 0) {
    const renderedArgs = [command, ...args].join(' ')
    throw new Error(`${renderedArgs} exited with code ${result.status ?? 'unknown'}`)
  }
}
