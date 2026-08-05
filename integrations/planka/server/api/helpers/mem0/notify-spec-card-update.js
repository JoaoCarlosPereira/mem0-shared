/*!
 * Mem0 Shared — notify Spec SoT after a human edits a mapped PLANKA card.
 */

const http = require('http');
const https = require('https');
const { URL } = require('url');

module.exports = {
  friendlyName: 'Notify Spec card update',

  description: 'Copies human-edited PLANKA card metadata back to its Spec task.',

  inputs: {
    plankaCardId: { type: 'string', required: true },
    name: { type: 'string', allowNull: true },
    description: { type: 'string', allowNull: true },
    dueDate: { type: 'string', allowNull: true },
    position: { type: 'number', allowNull: true },
    changedFields: { type: ['string'], required: true },
    actor: { type: 'string', allowNull: true },
  },

  exits: {
    success: { description: 'Bridge accepted the update (or ignored an unmapped card).' },
    rejected: { description: 'Spec rejected or could not persist the update.' },
  },

  async fn(inputs, exits) {
    const base = String(process.env.OPENMEMORY_INTERNAL_URL || '').trim().replace(/\/$/, '');
    const token = String(
      process.env.OPENMEMORY_BRIDGE_TOKEN || process.env.INTERNAL_ACCESS_TOKEN || '',
    ).trim();

    if (!base || !token) {
      sails.log.warn('mem0 notify-spec-card-update: OPENMEMORY_INTERNAL_URL/token missing');
      return exits.rejected({ error: 'bridge_not_configured' });
    }

    const body = JSON.stringify({
      planka_card_id: inputs.plankaCardId,
      name: inputs.name,
      description: inputs.description,
      due_date: inputs.dueDate,
      position: inputs.position,
      changed_fields: inputs.changedFields,
      actor: inputs.actor || 'ui-user',
    });
    const url = new URL(`${base}/api/v1/specs/planka/card-updated`);
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
          res.on('data', (chunk) => chunks.push(chunk));
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
    sails.log.warn('mem0 notify-spec-card-update rejected', result.status, result.body);
    return exits.rejected(result.body || { status: result.status });
  },
};
