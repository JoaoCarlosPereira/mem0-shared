module.exports = (boards, sameGroupUserIds, groupedUserIds) => {
  const sameGroupSet = new Set(sameGroupUserIds.map(String));
  const groupedUserSet = new Set(groupedUserIds.map(String));

  return boards.filter((board) => {
    if (!board.creatorUserId) {
      return true;
    }

    const creatorUserId = String(board.creatorUserId);
    return !groupedUserSet.has(creatorUserId) || sameGroupSet.has(creatorUserId);
  });
};
