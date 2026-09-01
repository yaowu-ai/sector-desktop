const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..')

for (const fileName of ['.env.production', '.env.test']) {
  const env = parseEnvFile(fs.readFileSync(path.join(root, fileName), 'utf8'))

  assert.ok(
    env.VITE_DESKTOP_API_BASE_URL,
    `${fileName} must define VITE_DESKTOP_API_BASE_URL`,
  )
  assert.ok(
    env.VITE_LICENSE_PUBLIC_KEY,
    `${fileName} must define VITE_LICENSE_PUBLIC_KEY`,
  )
  assert.ok(
    !env.VITE_LICENSE_PUBLIC_KEY.includes('REPLACE_WITH_LICENSE_VERIFY_PUBLIC_KEY'),
    `${fileName} must not use the placeholder License public key`,
  )
  assert.match(
    env.VITE_LICENSE_PUBLIC_KEY,
    /-----BEGIN PUBLIC KEY-----\\n.+\\n-----END PUBLIC KEY-----\\n?/,
    `${fileName} must contain a PEM public key encoded with escaped newlines`,
  )
}

console.log('desktop env file checks passed')

function parseEnvFile(content) {
  const values = {}

  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#')) continue

    const separatorIndex = trimmed.indexOf('=')
    if (separatorIndex < 1) continue

    values[trimmed.slice(0, separatorIndex).trim()] = trimmed
      .slice(separatorIndex + 1)
      .trim()
  }

  return values
}
