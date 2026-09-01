import { spawnSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const mode = normalizeMode(process.argv[2] || process.env.DESKTOP_BUILD_MODE || 'production')
const corepack = process.platform === 'win32' ? 'corepack.cmd' : 'corepack'

validateBuildEnv(mode)
run(corepack, ['pnpm', 'exec', 'tsc'])
run(corepack, ['pnpm', 'exec', 'vite', 'build', '--mode', mode])

function normalizeMode(value) {
  const normalized = String(value || '').trim().toLowerCase()

  if (normalized === 'test') return 'test'
  if (normalized === 'production' || normalized === 'prod' || normalized === '') return 'production'

  throw new Error(`Unsupported build mode: ${value}`)
}

function validateBuildEnv(mode) {
  if (mode !== 'production') return

  const env = loadViteEnv(mode)
  requireEnvValue(env, 'VITE_DESKTOP_API_BASE_URL')
  const publicKey = requireEnvValue(env, 'VITE_LICENSE_PUBLIC_KEY')

  if (publicKey.includes('REPLACE_WITH_LICENSE_VERIFY_PUBLIC_KEY')) {
    throw new Error('VITE_LICENSE_PUBLIC_KEY must not be the placeholder value for production builds')
  }

  if (!publicKey.includes('-----BEGIN PUBLIC KEY-----') || !publicKey.includes('-----END PUBLIC KEY-----')) {
    throw new Error('VITE_LICENSE_PUBLIC_KEY must be a PEM public key for production builds')
  }
}

function loadViteEnv(mode) {
  const files = ['.env', '.env.local', `.env.${mode}`, `.env.${mode}.local`]
  const values = {}

  for (const file of files) {
    const fullPath = resolve(file)
    if (!existsSync(fullPath)) continue

    Object.assign(values, parseEnvFile(readFileSync(fullPath, 'utf8')))
  }

  return { ...values, ...process.env }
}

function parseEnvFile(content) {
  const values = {}

  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#')) continue

    const separatorIndex = trimmed.indexOf('=')
    if (separatorIndex < 1) continue

    const key = trimmed.slice(0, separatorIndex).trim()
    let value = trimmed.slice(separatorIndex + 1).trim()
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1)
    }
    values[key] = value
  }

  return values
}

function requireEnvValue(env, name) {
  const value = String(env[name] || '').trim()
  if (!value) {
    throw new Error(`${name} is required for production desktop builds`)
  }
  return value
}

function run(command, args) {
  const result = spawnSync(command, args, {
    stdio: 'inherit',
    env: process.env,
    shell: process.platform === 'win32',
  })

  if (result.error) {
    throw result.error
  }

  if (result.status !== 0) {
    const renderedArgs = [command, ...args].join(' ')
    throw new Error(`${renderedArgs} exited with code ${result.status ?? 'unknown'}`)
  }
}
