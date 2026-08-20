const assert = require('assert');

const filterBoardsByGroup = require('../../utils/filter-boards-by-group');

describe('filterBoardsByGroup', () => {
  const boards = [
    { id: 'technical', creatorUserId: 'service-user' },
    { id: 'same-group', creatorUserId: 'group-a-user' },
    { id: 'other-group', creatorUserId: 'group-b-user' },
    { id: 'legacy', creatorUserId: null },
  ];

  it('keeps technical and legacy boards while excluding boards from other groups', () => {
    const result = filterBoardsByGroup(boards, ['group-a-user'], ['group-a-user', 'group-b-user']);

    assert.deepStrictEqual(
      result.map(({ id }) => id),
      ['technical', 'same-group', 'legacy'],
    );
  });

  it('fails closed when group visibility cannot be resolved', () => {
    const result = filterBoardsByGroup(boards, [], [], {
      restrictUnknownCreators: true,
    });

    assert.deepStrictEqual(result.map(({ id }) => id), []);
  });

  it('uses the workspace group when a technical user created the board', () => {
    const result = filterBoardsByGroup(boards, ['group-a-user'], ['group-a-user', 'group-b-user'], {
      boardGroupIds: { technical: 'group-b' },
      currentGroupId: 'group-a',
    });

    assert.deepStrictEqual(
      result.map(({ id }) => id),
      ['same-group', 'legacy'],
    );
  });
});
