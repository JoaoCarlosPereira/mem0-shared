module.exports = async (query, user) => {
  if (!user || !user.email) {
    return null;
  }

  const groupResult = await query(
    `SELECT group_id
       FROM public.users
      WHERE lower(email) = lower($1)
        AND group_id IS NOT NULL
      LIMIT 1`,
    [user.email],
  );
  const result = await query(
    `SELECT ua.id, grouped_user.group_id = $1 AS same_group
       FROM planka.user_account AS ua
       JOIN public.users AS grouped_user
         ON lower(grouped_user.email) = lower(ua.email)
      WHERE grouped_user.group_id IS NOT NULL`,
    [groupResult.rows[0] ? groupResult.rows[0].group_id : null],
  );

  return {
    currentGroupId: groupResult.rows[0] ? String(groupResult.rows[0].group_id) : null,
    restrictUnknownCreators: true,
    groupedUserIds: result.rows.map(({ id }) => String(id)),
    sameGroupUserIds: result.rows
      .filter(({ same_group: sameGroup }) => sameGroup)
      .map(({ id }) => String(id)),
  };
};
