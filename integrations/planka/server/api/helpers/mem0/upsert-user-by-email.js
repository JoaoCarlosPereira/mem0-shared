/*!
 * Mem0 Shared — upsert PLANKA user_account by email (SSO-style, no password).
 * Shared by JWT embed auth and Spec→card assignee mirror.
 */

module.exports = {
  friendlyName: 'Upsert user by email',

  description: 'Creates or updates a PLANKA user keyed by email for Mem0 identities.',

  inputs: {
    email: { type: 'string', required: true },
    name: { type: 'string', allowNull: true },
    picture: { type: 'string', allowNull: true },
    actorUser: { type: 'ref', required: true },
  },

  exits: {
    success: { description: 'User record ready.' },
  },

  async fn(inputs) {
    let email = String(inputs.email || '')
      .trim()
      .toLowerCase();
    if (!email || !email.includes('@')) {
      throw new Error('mem0 upsert-user-by-email: invalid email');
    }

    const name = String(inputs.name || email.split('@')[0] || 'Mem0 User').trim().slice(0, 128);
    const picture = String(inputs.picture || '').trim();
    const avatar = picture ? { externalUrl: picture } : null;

    // Hostname aliases (s0293@mem0.local) must not create a second board member
    // when the Google-linked person already exists with the same avatar.
    if (email.endsWith('@mem0.local') && picture) {
      try {
        const result = await sails.sendNativeQuery(
          `SELECT id FROM planka.user_account
           WHERE is_deactivated = false
             AND email NOT LIKE '%@mem0.local'
             AND avatar->>'externalUrl' = $1
           ORDER BY id ASC
           LIMIT 1`,
          [picture],
        );
        const row = result && result.rows && result.rows[0];
        if (row && row.id) {
          const existingReal = await User.qm.getOneById(String(row.id));
          if (existingReal) {
            return existingReal;
          }
        }
      } catch (err) {
        sails.log.warn(
          'mem0 upsert-user-by-email: alias→real lookup failed:',
          err.message || err,
        );
      }
    }

    let user = await User.qm.getOneByEmail(email);
    if (!user) {
      try {
        user = await sails.helpers.users.createOne.with({
          values: {
            email,
            name,
            role: User.Roles.ADMIN,
            language: 'pt-BR',
            isSsoUser: true,
            avatar,
          },
          actorUser: inputs.actorUser,
        });
      } catch (err) {
        user = await User.qm.getOneByEmail(email);
        if (!user) {
          throw err;
        }
      }
    } else {
      const values = {};
      if (name && name !== user.name) values.name = name;
      if (user.language !== 'pt-BR') values.language = 'pt-BR';
      if (user.isDeactivated) values.isDeactivated = false;
      if (user.role !== User.Roles.ADMIN) values.role = User.Roles.ADMIN;
      if (picture) {
        const prevUrl =
          user.avatar && typeof user.avatar === 'object' ? user.avatar.externalUrl : null;
        if (prevUrl !== picture) {
          values.avatar = { externalUrl: picture };
        }
      }
      if (Object.keys(values).length > 0) {
        try {
          user = await sails.helpers.users.updateOne.with({
            record: user,
            values,
            actorUser: inputs.actorUser,
          });
        } catch (err) {
          sails.log.warn('mem0 upsert-user-by-email: update failed:', err.message || err);
        }
      }
    }

    return user;
  },
};
