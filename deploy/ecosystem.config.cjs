const path = require('node:path');
const root = path.resolve(__dirname, '..');
module.exports = { apps: [{
  name: 'conversational-ai',
  cwd: root,
  script: path.join(root, '.venv/bin/python'),
  args: '-m uvicorn preview_server:app --host 0.0.0.0 --port 20311',
  interpreter: 'none',
  autorestart: true,
  restart_delay: 3000,
  max_restarts: 10,
  time: true,
  out_file: path.join(root, '.runtime/app-out.log'),
  error_file: path.join(root, '.runtime/app-error.log'),
  env: { DEBUG: 'False', HOST: '0.0.0.0', PORT: '20311' }
}] };
