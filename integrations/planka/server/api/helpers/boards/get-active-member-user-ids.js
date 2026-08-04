module.exports = {
  inputs: {
    cards: { type: 'ref', required: true },
    cardMemberships: { type: 'ref', required: true },
    comments: { type: 'ref', required: true },
    actions: { type: 'ref', required: true },
    attachments: { type: 'ref', required: true },
    tasks: { type: 'ref', required: true },
  },

  async fn(inputs) {
    const { cards, cardMemberships, comments, actions, attachments, tasks } = inputs;
    
    const getUserIds = (records, field) => records.map((record) => record[field]).filter(Boolean);

    return [...new Set([
      ...getUserIds(cards, 'creatorUserId'),
      ...getUserIds(cardMemberships, 'userId'),
      ...getUserIds(comments, 'userId'),
      ...getUserIds(actions, 'userId'),
      ...getUserIds(attachments, 'creatorUserId'),
      ...getUserIds(tasks, 'assigneeUserId'),
    ])];
  }
};
