/*!
 * Mem0 Shared — project home groups: archived + completed (collapsed).
 */

module.exports.up = async (knex) => {
  await knex.schema.alterTable('project', (table) => {
    table.boolean('is_archived').notNullable().defaultTo(false);
    table.boolean('is_completed').notNullable().defaultTo(false);
  });

  return knex.schema.alterTable('project', (table) => {
    table.boolean('is_archived').notNullable().alter();
    table.boolean('is_completed').notNullable().alter();
  });
};

module.exports.down = (knex) =>
  knex.schema.alterTable('project', (table) => {
    table.dropColumn('is_archived');
    table.dropColumn('is_completed');
  });
