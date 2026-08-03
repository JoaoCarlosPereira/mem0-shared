/*!
 * Mem0 Shared — PLANKA auth bridge helpers (fail-closed when AUTH_JWT_SECRET is set).
 * Pure Node module (no Sails) so unit tests can run without lifting the app.
 */

'use strict';

const crypto = require('crypto');
const jwt = require('jsonwebtoken');

/**
 * @param {string|undefined|null} header
 * @returns {string}
 */
function bearerToken(header) {
  const h = String(header || '').trim();
  if (!h) return '';
  const prefix = 'Bearer ';
  if (h.length > prefix.length && h.slice(0, prefix.length).toLowerCase() === prefix.toLowerCase()) {
    return h.slice(prefix.length).trim();
  }
  return '';
}

/**
 * Synchronous Mem0 credential check (JWT / legacy / internal).
 * omtk_ tokens need async DB lookup — see authenticateOmtk.
 *
 * @param {{ authorizationHeader?: string, env?: NodeJS.ProcessEnv }} input
 * @returns {{ ok: boolean, method?: string, subject?: string, email?: string, reason?: string, needsOmtkLookup?: boolean, token?: string }}
 */
function authenticateMem0Request(input = {}) {
  const env = input.env || process.env;
  const secret = String(env.AUTH_JWT_SECRET || '').trim();

  if (!secret) {
    return { ok: true, method: 'disabled' };
  }

  const raw = bearerToken(input.authorizationHeader);
  if (!raw) {
    return { ok: false, reason: 'missing_token' };
  }

  const internal = String(env.INTERNAL_ACCESS_TOKEN || '').trim();
  if (internal && raw === internal) {
    return { ok: true, method: 'internal', subject: 'internal' };
  }

  if (String(env.MEM0_AUTH_ALLOW_LEGACY || '').trim() === '1' && raw === 'local') {
    return { ok: true, method: 'legacy', subject: 'legacy' };
  }

  if (raw.startsWith('omtk_')) {
    return { ok: false, reason: 'omtk_pending', needsOmtkLookup: true, token: raw };
  }

  try {
    const payload = jwt.verify(raw, secret, { algorithms: ['HS256'] });
    let sub = payload && payload.sub;
    if (typeof sub === 'number') {
      sub = String(sub);
    }
    if (sub === undefined || sub === null || String(sub).trim() === '') {
      return { ok: false, reason: 'missing_sub' };
    }
    return {
      ok: true,
      method: 'jwt',
      subject: String(sub),
      email: payload.email ? String(payload.email) : undefined,
    };
  } catch (_err) {
    return { ok: false, reason: 'invalid_jwt' };
  }
}

/**
 * Lookup omtk_ agent token against public.agent_tokens (OpenMemory DB).
 *
 * @param {string} rawToken
 * @param {{ query: (sql: string, params: unknown[]) => Promise<{ rows: Array<{ user_id: string, revoked_at: Date|null }> }> }} db
 * @returns {Promise<{ ok: boolean, method?: string, subject?: string, reason?: string }>}
 */
async function authenticateOmtk(rawToken, db) {
  if (!rawToken || !rawToken.startsWith('omtk_') || !db || typeof db.query !== 'function') {
    return { ok: false, reason: 'omtk_unavailable' };
  }
  const digest = crypto.createHash('sha256').update(rawToken, 'utf8').digest('hex');
  try {
    const result = await db.query(
      `SELECT user_id::text AS user_id, revoked_at
         FROM public.agent_tokens
        WHERE token_hash = $1
        LIMIT 1`,
      [digest],
    );
    const row = result && result.rows && result.rows[0];
    if (!row || !row.user_id || row.revoked_at) {
      return { ok: false, reason: 'omtk_invalid' };
    }
    return { ok: true, method: 'omtk_', subject: String(row.user_id) };
  } catch (_err) {
    return { ok: false, reason: 'omtk_lookup_failed' };
  }
}

module.exports = {
  bearerToken,
  authenticateMem0Request,
  authenticateOmtk,
};
