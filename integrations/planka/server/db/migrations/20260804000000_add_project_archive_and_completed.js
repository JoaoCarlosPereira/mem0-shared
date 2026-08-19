/*!
 * Mem0 Shared — project home groups: archived + completed (collapsed).
 */

module.exports.up = async (knex) => {
  const hasArchived = await knex.schema.hasColumn('project', 'is_archived');
  const hasCompleted = await knex.schema.hasColumn('project', 'is_completed');

  if (!hasArchived || !hasCompleted) {
    await knex.schema.alterTable('project', (table) => {
      if (!hasArchived) {
        table.boolean('is_archived').notNullable().defaultTo(false);
      }
      if (!hasCompleted) {
        table.boolean('is_completed').notNullable().defaultTo(false);
      }
    });
  }

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
