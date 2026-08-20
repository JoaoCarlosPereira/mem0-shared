module.exports = (
  boards,
  sameGroupUserIds = [],
  groupedUserIds = [],
  { restrictUnknownCreators = false, boardGroupIds = {}, currentGroupId = null } = {},
) => {
  const sameGroupSet = new Set(sameGroupUserIds.map(String));
  const groupedUserSet = new Set(groupedUserIds.map(String));

  return boards.filter((board) => {
    if (!board.creatorUserId) {
      return !restrictUnknownCreators;
    }

    const boardGroupId = boardGroupIds[String(board.id)];
    if (boardGroupId) {
      return String(boardGroupId) === String(currentGroupId);
    }

    const creatorUserId = String(board.creatorUserId);
    if (restrictUnknownCreators) {
      return sameGroupSet.has(creatorUserId);
    }

    return !groupedUserSet.has(creatorUserId) || sameGroupSet.has(creatorUserId);
  });
};
