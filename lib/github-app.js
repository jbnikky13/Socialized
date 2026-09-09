const crypto = require('crypto');

function requiredEnv(name) {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is not configured`);
  return value;
}

function base64url(value) {
  return Buffer.from(value).toString('base64url');
}

function createAppJwt() {
  const appId = requiredEnv('GITHUB_APP_ID');
  const privateKey = requiredEnv('GITHUB_APP_PRIVATE_KEY').replace(/\\n/g, '\n').trim();
  const now = Math.floor(Date.now() / 1000);
  const header = base64url(JSON.stringify({ alg: 'RS256', typ: 'JWT' }));
  const payload = base64url(JSON.stringify({ iat: now - 30, exp: now + 540, iss: String(appId) }));
  const unsigned = `${header}.${payload}`;
  const signer = crypto.createSign('RSA-SHA256');
  signer.update(unsigned);
  signer.end();
  return `${unsigned}.${signer.sign(privateKey, 'base64url')}`;
}

async function createInstallationToken() {
  const installationId = requiredEnv('GITHUB_APP_INSTALLATION_ID');
  const jwt = createAppJwt();
  const response = await fetch(`https://api.github.com/app/installations/${encodeURIComponent(installationId)}/access_tokens`, {
    method: 'POST',
    headers: {
      Accept: 'application/vnd.github+json',
      Authorization: `Bearer ${jwt}`,
      'X-GitHub-Api-Version': '2022-11-28',
      'Content-Type': 'application/json',
    },
  });
  const text = await response.text();
  let data;
  try { data = text ? JSON.parse(text) : {}; } catch { data = { message: text }; }
  if (!response.ok) throw new Error(`GitHub App installation token failed (HTTP ${response.status}): ${data.message || text.slice(0, 300)}`);
  if (!data.token) throw new Error('GitHub did not return an installation token');
  return data.token;
}

async function dispatchRenderRequested() {
  const owner = process.env.GITHUB_REPO_OWNER || 'jbnikky13';
  const repo = process.env.GITHUB_REPO_NAME || 'Socialized';
  const token = await createInstallationToken();
  const response = await fetch(`https://api.github.com/repos/${owner}/${repo}/dispatches`, {
    method: 'POST',
    headers: {
      Accept: 'application/vnd.github+json',
      Authorization: `Bearer ${token}`,
      'X-GitHub-Api-Version': '2022-11-28',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ event_type: 'render_requested', client_payload: { source: 'socialized-vercel' } }),
  });
  const text = await response.text();
  if (!response.ok) {
    let message = text;
    try { message = JSON.parse(text).message || text; } catch {}
    throw new Error(`GitHub render dispatch failed (HTTP ${response.status}): ${message.slice(0, 500)}`);
  }
  return { dispatched: true, event_type: 'render_requested' };
}

module.exports = { dispatchRenderRequested, createInstallationToken };
