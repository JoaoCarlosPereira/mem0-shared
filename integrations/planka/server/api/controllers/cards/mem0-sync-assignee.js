/*!
 * Mem0 Shared — Spec mirror sets card assignee (card_membership) by email.
 *
 * PUT /api/cards/:cardId/mem0-assignee
 * Body: { email: string|null, name?: string, picture?: string }
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
    const { currentUser } = this.req;

    const result = await sails.helpers.mem0.syncCardAssignee
      .with({
        cardId: inputs.cardId,
        email: inputs.email,
        name: inputs.name,
        picture: inputs.picture,
        actorUser: currentUser,
        request: this.req,
      })
      .intercept('cardNotFound', () => Errors.CARD_NOT_FOUND);

    return {
      item: result,
    };
  },
};
