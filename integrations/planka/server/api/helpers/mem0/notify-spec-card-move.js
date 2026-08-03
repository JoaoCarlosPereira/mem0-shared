/*!
 * Mem0 Shared — notify Spec SoT after a PLANKA card list move (ADR-007).
 */

const http = require('http');
const https = require('https');
const { URL } = require('url');

module.exports = {
  friendlyName: 'Notify Spec card move',

  description: 'Calls OpenMemory Spec bridge after a human moves a Spec-mapped card.',

  inputs: {
    plankaCardId: { type: 'string', required: true },
    plankaListId: { type: 'string', required: true },
    previousListId: { type: 'string', allowNull: true },
    actor: { type: 'string', allowNull: true },
  },

  exits: {
    success: { description: 'Bridge accepted the move (or ignored unmapped card).' },
    rejected: { description: 'Spec policy/OCC rejected the move.' },
  },

  async fn(inputs, exits) {
    const base = String(process.env.OPENMEMORY_INTERNAL_URL || '').trim().replace(/\/$/, '');
    const token = String(
      process.env.OPENMEMORY_BRIDGE_TOKEN || process.env.INTERNAL_ACCESS_TOKEN || '',
    ).trim();

    if (!base || !token) {
      sails.log.warn('mem0 notify-spec-card-move: OPENMEMORY_INTERNAL_URL/token missing; skip');
      return exits.success({ skipped: true });
    }

    const body = JSON.stringify({
      planka_card_id: inputs.plankaCardId,
      planka_list_id: inputs.plankaListId,
      actor: inputs.actor || 'ui-user',
    });

    const url = new URL(`${base}/api/v1/specs/planka/card-moved`);
    const transport = url.protocol === 'https:' ? https : http;

    const result = await new Promise((resolve) => {
      const req = transport.request(
        {
          protocol: url.protocol,
          hostname: url.hostname,
          port: url.port || (url.protocol === 'https:' ? 443 : 80),
          path: url.pathname,
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(body),
            Authorization: `Bearer ${token}`,
          },
          timeout: 8000,
        },
        (res) => {
          const chunks = [];
          res.on('data', (c) => chunks.push(c));
          res.on('end', () => {
            const text = Buffer.concat(chunks).toString('utf8');
            let parsed = null;
            try {
              parsed = text ? JSON.parse(text) : null;
            } catch (_err) {
              parsed = { raw: text };
            }
            resolve({ status: res.statusCode || 0, body: parsed });
          });
        },
      );
      req.on('error', (err) => resolve({ status: 0, body: { error: err.message } }));
      req.on('timeout', () => {
        req.destroy();
        resolve({ status: 0, body: { error: 'timeout' } });
      });
      req.write(body);
      req.end();
    });

    if (result.status >= 200 && result.status < 300) {
      return exits.success(result.body || { ok: true });
    }

    sails.log.warn('mem0 notify-spec-card-move rejected', result.status, result.body);
    return exits.rejected(result.body || { status: result.status });
  },
};
