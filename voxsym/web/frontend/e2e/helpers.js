import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import path from 'path';
import { setTimeout } from 'timers/promises';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '../../../..');

export async function startBackend() {
  const backendPath = path.join(__dirname, '_backend.py');
  const pythonBin = path.join(REPO_ROOT, '.venv', 'bin', 'python');

  const proc = spawn(
    pythonBin,
    ['-u', backendPath],
    {
      cwd: REPO_ROOT,
      stdio: 'pipe',
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
    },
  );

  let lastErr = '';
  proc.stderr.on('data', (chunk) => {
    lastErr += chunk.toString();
  });

  for (let i = 0; i < 50; i++) {
    try {
      const res = await fetch('http://0.0.0.0:8080/');
      if (res.status === 200) return proc;
    } catch {}
    if (proc.exitCode !== null) {
      throw new Error(`backend exited with ${proc.exitCode}: ${lastErr}`);
    }
    await setTimeout(200);
  }
  proc.kill();
  throw new Error('backend did not start within 10s');
}

export function stopBackend(proc) {
  if (!proc) return;
  proc.kill('SIGTERM');
}
