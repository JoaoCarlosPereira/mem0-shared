/*!
 * Mem0 Shared — project Spec assignee onto PLANKA card_membership (single member).
 */

module.exports = {
  friendlyName: 'Sync card assignee',

  description:
    'Ensures the card has exactly one membership for the Spec assignee (or none if cleared).',

  inputs: {
    cardId: { type: 'string', required: true },
    email: { type: 'string', allowNull: true },
    name: { type: 'string', allowNull: true },
    picture: { type: 'string', allowNull: true },
    actorUser: { type: 'ref', required: true },
    request: { type: 'ref' },
  },

  exits: {
    success: { description: 'Card memberships synced.' },
    cardNotFound: { description: 'Card not found.' },
  },

  async fn(inputs, exits) {
    const path = await sails.helpers.cards
      .getPathToProjectById(inputs.cardId)
      .tolerate('pathNotFound', () => null);

    if (!path) {
      return exits.cardNotFound();
    }

    const { card, list, board, project } = path;
    const existing = await CardMembership.qm.getByCardId(card.id);

    const deleteMembership = async (membership) => {
      const memberUser = await User.qm.getOneById(membership.userId);
      if (!memberUser) {
        await CardMembership.qm.deleteOne(membership.id);
        return;
      }
      await sails.helpers.cardMemberships.deleteOne.with({
        user: memberUser,
        project,
        board,
        list,
        card,
        record: membership,
        actorUser: inputs.actorUser,
        request: inputs.request,
      });
    };

    const rawEmail = inputs.email == null ? '' : String(inputs.email).trim();
    if (!rawEmail) {
      // Release / no assignee → clear Spec-mirrored members.
      // eslint-disable-next-line no-restricted-syntax
      for (const membership of existing || []) {
        // eslint-disable-next-line no-await-in-loop
        await deleteMembership(membership);
      }
      return exits.success({ cleared: true, userId: null });
    }

    const user = await sails.helpers.mem0.upsertUserByEmail.with({
      email: rawEmail,
      name: inputs.name,
      picture: inputs.picture,
      actorUser: inputs.actorUser,
    });

    // Card membership requires board membership (no admin bypass).
    let boardMembership = await BoardMembership.qm.getOneByBoardIdAndUserId(board.id, user.id);
    if (!boardMembership) {
      const existingPm = await ProjectManager.qm.getOneByProjectIdAndUserId(project.id, user.id);
      if (!existingPm) {
        await ProjectManager.qm.createOne({
          projectId: project.id,
          userId: user.id,
        });
      }
      boardMembership = await BoardMembership.qm.createOne({
        projectId: project.id,
        boardId: board.id,
        userId: user.id,
        role: BoardMembership.Roles.EDITOR,
      });
    } else if (boardMembership.role !== BoardMembership.Roles.EDITOR) {
      boardMembership = await BoardMembership.qm.updateOne(boardMembership.id, {
        role: BoardMembership.Roles.EDITOR,
      });
    }

    // eslint-disable-next-line no-restricted-syntax
    for (const membership of existing || []) {
      if (membership.userId === user.id) continue;
      // eslint-disable-next-line no-await-in-loop
      await deleteMembership(membership);
    }

    const already = (existing || []).some((m) => m.userId === user.id);
    if (!already) {
      await sails.helpers.cardMemberships.createOne
        .with({
          project,
          board,
          list,
          values: { card, user },
          actorUser: inputs.actorUser,
          request: inputs.request,
        })
        .tolerate('userAlreadyCardMember', () => null);
    }

    return exits.success({ cleared: false, userId: user.id, email: user.email });
  },
};
