/*!
 * Mem0 Shared — create a mirrored Spec comment as its real author.
 *
 * POST /api/cards/:cardId/mem0-comments
 * Body: { text, email?, name?, picture? }
 */

const { idInput } = require('../../../utils/inputs');

const Errors = {
  CARD_NOT_FOUND: {
    cardNotFound: 'Card not found',
  },
};

module.exports = {
  inputs: {
    cardId: {
      ...idInput,
      required: true,
    },
    text: {
      type: 'string',
      maxLength: 1048576,
      required: true,
    },
    email: {
      type: 'string',
      isNotEmptyString: true,
      maxLength: 256,
      allowNull: true,
    },
    name: {
      type: 'string',
      isNotEmptyString: true,
      maxLength: 128,
      allowNull: true,
    },
    picture: {
      type: 'string',
      isNotEmptyString: true,
      maxLength: 2048,
      allowNull: true,
    },
  },

  exits: {
    cardNotFound: {
      responseType: 'notFound',
    },
  },

  async fn(inputs) {
    const serviceUser = this.req.currentUser;
    const { card, list, board, project } = await sails.helpers.cards
      .getPathToProjectById(inputs.cardId)
      .intercept('pathNotFound', () => Errors.CARD_NOT_FOUND);

    let authorUser = serviceUser;
    if (inputs.email) {
      authorUser = await sails.helpers.mem0.upsertUserByEmail.with({
        email: inputs.email,
        name: inputs.name,
        picture: inputs.picture,
        actorUser: serviceUser,
      });
    }
    if (!authorUser || !authorUser.id) {
      return this.res.status(503).json({
        code: 'E_MEM0_COMMENT_AUTHOR',
        message: 'Could not resolve mirrored comment author',
      });
    }

    const comment = await sails.helpers.comments.createOne.with({
      project,
      board,
      list,
      values: {
        text: inputs.text,
        card,
        user: authorUser,
      },
      request: this.req,
    });

    return {
      item: comment,
    };
  },
};
