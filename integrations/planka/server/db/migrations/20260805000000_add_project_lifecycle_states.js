/*!
 * Copyright (c) 2024 PLANKA Software GmbH
 * Licensed under the Fair Use License: https://github.com/plankanban/planka/blob/master/LICENSE.md
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
