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

    // PLANKA's next_id() uses unqualified nextval('next_id_seq'). When the
    // Waterline connection does not honor search_path options, qualify it.
    const fn = await client.query(
      `SELECT pg_get_functiondef(p.oid) AS def
         FROM pg_proc p
         JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = $1 AND p.proname = 'next_id'
        LIMIT 1`,
      [schema],
    );
    if (fn.rows[0] && fn.rows[0].def && !fn.rows[0].def.includes(`${schema}.next_id_seq`)) {
      const patched = String(fn.rows[0].def).replace(
        /nextval\('next_id_seq'\)/g,
        `nextval('${schema}.next_id_seq')`,
      );
      await client.query(patched);
      console.log(`ensure-schema: patched ${schema}.next_id() to use qualified sequence`);
    }

    // Some Sails queries run with search_path that omits the planka schema.
    // Expose an unqualified next_id() in public that delegates to schema.next_id().
    await client.query(`
      CREATE OR REPLACE FUNCTION public.next_id(OUT result bigint) AS $$
      BEGIN
        SELECT ${ident}.next_id() INTO result;
      END;
      $$ LANGUAGE PLPGSQL;
    `);


    // Waterline/Knex often omit search_path=planka; expose auto-updatable
    // public views for tables hit by card update / assignee sync.
    // Table names match Knex/Waterline (User model → user_account).
    const mirrorTables = [
      'notification',
      'action',
      'card_membership',
      'card_subscription',
      'board_membership',
      'card',
      'list',
      'user_account',
    ];
    for (const table of mirrorTables) {
      const q = quoteIdent(table);
      const exists = await client.query(
        `SELECT 1 FROM information_schema.tables
          WHERE table_schema = $1 AND table_name = $2`,
        [schema, table],
      );
      if (!exists.rowCount) {
        console.warn(`ensure-schema: skip missing ${schema}.${table}`);
        continue;
      }
      await client.query(
        `CREATE OR REPLACE VIEW public.${q} AS SELECT * FROM ${ident}.${q}`,
      );
    }
    console.log(`ensure-schema: public views mirrored for planka tables`);

    console.log(`ensure-schema: schema ${schema} ready`);
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error('ensure-schema failed:', err.message || err);
  process.exit(1);
});
