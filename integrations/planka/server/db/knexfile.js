/*!
 * Copyright (c) 2024 PLANKA Software GmbH
 * Licensed under the Fair Use License: https://github.com/plankanban/planka/blob/master/LICENSE.md
 */

const path = require('path');
const dotenv = require('dotenv');
const _ = require('lodash');

dotenv.config({
  path: path.resolve(__dirname, '../.env'),
  quiet: true,
});

function buildSSLConfig() {
  if (process.env.KNEX_REJECT_UNAUTHORIZED_SSL_CERTIFICATE === 'false') {
    return {
      rejectUnauthorized: false,
    };
  }

  return false;
}

// Mem0 Shared: isolate PLANKA tables into schema `planka` (same DB as openmemory).
const mem0Schema = String(process.env.MEM0_PG_SCHEMA || '').trim();

module.exports = {
  client: 'pg',
  ...(mem0Schema ? { searchPath: [mem0Schema, 'public'] } : {}),
  connection: {
    connectionString: process.env.DATABASE_URL,
    ssl: buildSSLConfig(),
  },
  migrations: {
    tableName: 'migration',
    directory: path.join(__dirname, 'migrations'),
  },
  seeds: {
    directory: path.join(__dirname, 'seeds'),
  },
  wrapIdentifier: (value, origImpl) => origImpl(_.snakeCase(value)),
};
