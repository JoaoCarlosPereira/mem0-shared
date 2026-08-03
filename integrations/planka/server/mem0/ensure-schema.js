/*!
 * Mem0 Shared — ensure PostgreSQL schema `planka` exists before Knex migrate.
 * Uses DATABASE_URL against the shared OpenMemory database (not Qdrant).
 */

'use strict';

const { Client } = require('pg');

function quoteIdent(name) {
  if (!/^[a-z_][a-z0-9_]*$/i.test(name)) {
    throw new Error(`Invalid schema name: ${name}`);
  }
  return `"${name}"`;
}

async function main() {
  const schema = String(process.env.MEM0_PG_SCHEMA || 'planka').trim() || 'planka';
  const dsn = String(process.env.DATABASE_URL || '').trim();
  if (!dsn) {
    console.error('ensure-schema: DATABASE_URL is required');
    process.exit(1);
  }

  const client = new Client({ connectionString: dsn });
  await client.connect();
  try {
    const ident = quoteIdent(schema);
    await client.query(`CREATE SCHEMA IF NOT EXISTS ${ident}`);
    await client.query(`GRANT ALL ON SCHEMA ${ident} TO CURRENT_USER`);
    await client.query(`GRANT ALL ON SCHEMA ${ident} TO PUBLIC`);
    console.log(`ensure-schema: schema ${schema} ready`);
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error('ensure-schema failed:', err.message || err);
  process.exit(1);
});
