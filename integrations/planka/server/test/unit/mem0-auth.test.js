/*!
 * Unit tests for Mem0 PLANKA auth bridge (no Sails lift).
 * Run: npm test -- --grep mem0-auth  (from server/) or:
 *   node --test test/unit/mem0-auth.test.js
 */

const assert = require('assert');
const crypto = require('crypto');
const jwt = require('jsonwebtoken');
const { describe, it } = require('node:test');

const {
  bearerToken,
  authenticateMem0Request,
  authenticateOmtk,
} = require('../../api/hooks/mem0-auth/lib/validate-auth');

const SECRET = 'unit-test-secret-value-32bytes!!';

describe('mem0-auth validate-auth', () => {
  it('bearerToken parses Authorization header', () => {
    assert.strictEqual(bearerToken('Bearer abc'), 'abc');
    assert.strictEqual(bearerToken('bearer xyz'), 'xyz');
    assert.strictEqual(bearerToken(''), '');
    assert.strictEqual(bearerToken(undefined), '');
  });

  it('bridge disabled when AUTH_JWT_SECRET empty', () => {
    const r = authenticateMem0Request({
      authorizationHeader: '',
      env: { AUTH_JWT_SECRET: '' },
    });
    assert.strictEqual(r.ok, true);
    assert.strictEqual(r.method, 'disabled');
  });

  it('allows the bootstrap route without a token so the login screen can load', () => {
    const r = authenticateMem0Request({
      authorizationHeader: '',
      path: '/api/bootstrap',
      env: { AUTH_JWT_SECRET: SECRET },
    });
    assert.strictEqual(r.ok, true);
    assert.strictEqual(r.method, 'public');
  });

  it('keeps protected API routes fail-closed without a token', () => {
    const r = authenticateMem0Request({
      authorizationHeader: '',
      path: '/api/users/me',
      env: { AUTH_JWT_SECRET: SECRET },
    });
    assert.strictEqual(r.ok, false);
    assert.strictEqual(r.reason, 'missing_token');
  });

  it('accepts HS256 JWT with sub', () => {
    const token = jwt.sign({ sub: 'user-1', email: 'a@example.com' }, SECRET, {
      algorithm: 'HS256',
    });
    const r = authenticateMem0Request({
      authorizationHeader: `Bearer ${token}`,
      env: { AUTH_JWT_SECRET: SECRET },
    });
    assert.strictEqual(r.ok, true);
    assert.strictEqual(r.method, 'jwt');
    assert.strictEqual(r.subject, 'user-1');
  });

  it('propagates name picture and mem0 claim from JWT', () => {
    const token = jwt.sign(
      {
        sub: 'joao@example.com',
        email: 'joao@example.com',
        name: 'João',
        picture: 'https://lh3.example/p.jpg',
        mem0: true,
      },
      SECRET,
      { algorithm: 'HS256' },
    );
    const r = authenticateMem0Request({
      authorizationHeader: `Bearer ${token}`,
      env: { AUTH_JWT_SECRET: SECRET },
    });
    assert.strictEqual(r.ok, true);
    assert.strictEqual(r.method, 'jwt');
    assert.strictEqual(r.email, 'joao@example.com');
    assert.strictEqual(r.name, 'João');
    assert.strictEqual(r.picture, 'https://lh3.example/p.jpg');
    assert.strictEqual(r.mem0, true);
  });

  it('propagates the trusted group claim from JWT (kanban-board-group-isolation)', () => {
    const token = jwt.sign(
      {
        sub: 'u1@example.com',
        email: 'u1@example.com',
        group: '11111111-2222-3333-4444-555555555555',
      },
      SECRET,
      { algorithm: 'HS256' },
    );
    const r = authenticateMem0Request({
      authorizationHeader: `Bearer ${token}`,
      env: { AUTH_JWT_SECRET: SECRET },
    });
    assert.strictEqual(r.ok, true);
    assert.strictEqual(r.method, 'jwt');
    assert.strictEqual(r.group, '11111111-2222-3333-4444-555555555555');
  });

  it('leaves group undefined when the JWT carries no group (fail-closed downstream)', () => {
    const token = jwt.sign({ sub: 'u2@example.com', email: 'u2@example.com' }, SECRET, {
      algorithm: 'HS256',
    });
    const r = authenticateMem0Request({
      authorizationHeader: `Bearer ${token}`,
      env: { AUTH_JWT_SECRET: SECRET },
    });
    assert.strictEqual(r.ok, true);
    assert.strictEqual(r.group, undefined);
  });

  it('rejects JWT signed with wrong secret', () => {
    const token = jwt.sign({ sub: 'user-1' }, 'other-secret-other-secret-xxxx', {
      algorithm: 'HS256',
    });
    const r = authenticateMem0Request({
      authorizationHeader: `Bearer ${token}`,
      env: { AUTH_JWT_SECRET: SECRET },
    });
    assert.strictEqual(r.ok, false);
    assert.strictEqual(r.reason, 'invalid_jwt');
  });

  it('rejects JWT without sub', () => {
    const token = jwt.sign({ email: 'a@example.com' }, SECRET, {
      algorithm: 'HS256',
    });
    const r = authenticateMem0Request({
      authorizationHeader: `Bearer ${token}`,
      env: { AUTH_JWT_SECRET: SECRET },
    });
    assert.strictEqual(r.ok, false);
    assert.strictEqual(r.reason, 'missing_sub');
  });

  it('allows public routes with query strings', () => {
    const r = authenticateMem0Request({
      authorizationHeader: '',
      path: '/api/terms?lang=pt-BR',
      env: { AUTH_JWT_SECRET: SECRET },
    });
    assert.strictEqual(r.ok, true);
    assert.strictEqual(r.method, 'public');
  });

  it('accepts Bearer local when MEM0_AUTH_ALLOW_LEGACY=1', () => {
    const r = authenticateMem0Request({
      authorizationHeader: 'Bearer local',
      env: { AUTH_JWT_SECRET: SECRET, MEM0_AUTH_ALLOW_LEGACY: '1' },
    });
    assert.strictEqual(r.ok, true);
    assert.strictEqual(r.method, 'legacy');
  });

  it('rejects Bearer local when legacy disabled', () => {
    const r = authenticateMem0Request({
      authorizationHeader: 'Bearer local',
      env: { AUTH_JWT_SECRET: SECRET, MEM0_AUTH_ALLOW_LEGACY: '0' },
    });
    assert.strictEqual(r.ok, false);
  });

  it('accepts INTERNAL_ACCESS_TOKEN', () => {
    const r = authenticateMem0Request({
      authorizationHeader: 'Bearer super-internal',
      env: { AUTH_JWT_SECRET: SECRET, INTERNAL_ACCESS_TOKEN: 'super-internal' },
    });
    assert.strictEqual(r.ok, true);
    assert.strictEqual(r.method, 'internal');
  });

  it('flags omtk_ for async lookup', () => {
    const r = authenticateMem0Request({
      authorizationHeader: 'Bearer omtk_abc',
      env: { AUTH_JWT_SECRET: SECRET },
    });
    assert.strictEqual(r.needsOmtkLookup, true);
    assert.strictEqual(r.token, 'omtk_abc');
  });

  it('authenticateOmtk accepts valid non-revoked token', async () => {
    const raw = 'omtk_testtoken';
    const digest = crypto.createHash('sha256').update(raw, 'utf8').digest('hex');
    const db = {
      async query(sql, params) {
        assert.ok(sql.includes('agent_tokens'));
        assert.strictEqual(params[0], digest);
        return { rows: [{ user_id: 'agent-9', revoked_at: null }] };
      },
    };
    const r = await authenticateOmtk(raw, db);
    assert.strictEqual(r.ok, true);
    assert.strictEqual(r.method, 'omtk_');
    assert.strictEqual(r.subject, 'agent-9');
  });

  it('authenticateOmtk rejects revoked token', async () => {
    const db = {
      async query() {
        return { rows: [{ user_id: 'agent-9', revoked_at: new Date() }] };
      },
    };
    const r = await authenticateOmtk('omtk_x', db);
    assert.strictEqual(r.ok, false);
    assert.strictEqual(r.reason, 'omtk_invalid');
  });
});
