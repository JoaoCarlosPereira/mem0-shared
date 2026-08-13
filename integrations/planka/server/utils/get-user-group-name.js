module.exports = async (query, email) => {
  if (!email) {
    return null;
  }

  const result = await query(
    `SELECT groups.name
       FROM public.users
       JOIN public.groups ON public.groups.id = public.users.group_id
      WHERE lower(public.users.email) = lower($1)
      LIMIT 1`,
    [email],
  );

  return result.rows[0] ? result.rows[0].name : null;
};
