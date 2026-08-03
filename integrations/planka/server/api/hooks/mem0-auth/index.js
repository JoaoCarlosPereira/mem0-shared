/*!
 * Mem0 Shared — fail-closed auth bridge for PLANKA `/api/*`.
 *
 * When AUTH_JWT_SECRET is set, every `/api/*` request must present one of:
 *   - HS256 JWT signed with AUTH_JWT_SECRET (same secret as Mem0 / NEXTAUTH_SECRET)
 *   - Authorization: Bearer local  (only if MEM0_AUTH_ALLOW_LEGACY=1)
 *   - INTERNAL_ACCESS_TOKEN (existing PLANKA internal bearer)
 *   - omtk_* agent token (lookup in public.agent_tokens on the shared Postgres)
 *
 * On success without a PLANKA session user, sets req.currentUser = User.INTERNAL
 * so existing is-authenticated policies pass for the OpenMemory BFF/mirror.
 *
 * When AUTH_JWT_SECRET is empty, the bridge is a no-op (upstream PLANKA auth only).
 */

const { Client } = require('pg');

const { authenticateMem0Request, authenticateOmtk } = require('./lib/validate-auth');

module.exports = function defineMem0AuthHook(sails) {
  let pgClient = null;
  let pgClientFailed = false;

  const getPgClient = async () => {
    if (pgClient) return pgClient;
    if (pgClientFailed) return null;
    const dsn = String(process.env.DATABASE_URL || '').trim();
    if (!dsn) {
      pgClientFailed = true;
      return null;
    }
    try {
      const client = new Client({ connectionString: dsn });
      await client.connect();
      pgClient = client;
      return pgClient;
    } catch (err) {
      pgClientFailed = true;
      sails.log.warn('mem0-auth: could not open Postgres for omtk_ lookup:', err.message);
      return null;
    }
  };

  return {
    async initialize() {
      sails.log.info('Initializing custom hook (`mem0-auth`)');
    },

    routes: {
      before: {
        '/api/*': {
          async fn(req, res, next) {
            const result = authenticateMem0Request({
              authorizationHeader: req.headers && req.headers.authorization,
              env: process.env,
            });

            if (result.method === 'disabled') {
              return next();
            }

            let auth = result;
            if (result.needsOmtkLookup) {
              const client = await getPgClient();
              auth = await authenticateOmtk(result.token, client);
            }

            if (!auth.ok) {
              return res.status(401).json({
                code: 'E_MEM0_UNAUTHORIZED',
                message: 'Mem0 authentication required',
                reason: auth.reason || 'unauthorized',
              });
            }

            req.mem0Auth = {
              method: auth.method,
              subject: auth.subject,
              email: auth.email,
            };

            if (!req.currentUser && typeof User !== 'undefined' && User.INTERNAL) {
              req.currentUser = User.INTERNAL;
            }

            return next();
          },
        },
      },
    },
  };
};
