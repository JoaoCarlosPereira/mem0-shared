module.exports = async (query, boards) => {
  const boardIds = boards.map(({ id }) => String(id));
  if (boardIds.length === 0) {
    return {};
  }

  const result = await query(
    `SELECT mapping.planka_id AS board_id, workspace.group_id::text AS group_id
       FROM public.spec_planka_id_map AS mapping
       JOIN public.spec_workspaces AS workspace
         ON workspace.id = mapping.spec_id
      WHERE mapping.entity_type = 'board'
        AND workspace.group_id IS NOT NULL
        AND mapping.planka_id = ANY($1::text[])`,
    [boardIds],
  );

  return result.rows.reduce((groupsByBoardId, row) => {
    // eslint-disable-next-line no-param-reassign
    groupsByBoardId[String(row.board_id)] = String(row.group_id);
    return groupsByBoardId;
  }, {});
};
