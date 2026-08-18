/*!
 * Mem0 Shared — persist the optional creator of a Kanban board.
 */

module.exports.up = async (knex) => {
  const hasColumn = await knex.schema.hasColumn('board', 'creator_user_id');
  if (!hasColumn) {
    await knex.schema.alterTable('board', (table) => {
      table.bigInteger('creator_user_id');
    });
  }
};

module.exports.down = async (knex) => {
  const hasColumn = await knex.schema.hasColumn('board', 'creator_user_id');
  if (hasColumn) {
    await knex.schema.alterTable('board', (table) => {
      table.dropColumn('creator_user_id');
    });
  }
};
