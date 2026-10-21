// Exit 0 if the production build is missing or older than any source file, else exit 1.
// Used by launch.bat / launch.sh so the UI is only rebuilt when something changed.
import { existsSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const built = path.join(root, 'dist', 'index.html')
if (!existsSync(built)) process.exit(0)
const builtAt = statSync(built).mtimeMs

function newest(target) {
  const stat = statSync(target)
  if (!stat.isDirectory()) return stat.mtimeMs
  return readdirSync(target).reduce((latest, name) => Math.max(latest, newest(path.join(target, name))), stat.mtimeMs)
}

const inputs = ['src', 'public', 'index.html', 'package.json', 'vite.config.ts'].map((p) => path.join(root, p)).filter(existsSync)
process.exit(inputs.some((p) => newest(p) > builtAt) ? 0 : 1)
