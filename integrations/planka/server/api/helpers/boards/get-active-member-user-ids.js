const getUserIds = (records, field) => records.map((record) => record[field]).filter(Boolean);

const getActiveMemberUserIds = ({
  cards,
  cardMemberships,
  comments,
  actions,
  attachments,
  tasks,
}) =>
  _.uniq([
    ...getUserIds(cards, 'creatorUserId'),
    ...getUserIds(cardMemberships, 'userId'),
    ...getUserIds(comments, 'userId'),
    ...getUserIds(actions, 'userId'),
    ...getUserIds(attachments, 'creatorUserId'),
    ...getUserIds(tasks, 'assigneeUserId'),
  ]);

module.exports = getActiveMemberUserIds;
