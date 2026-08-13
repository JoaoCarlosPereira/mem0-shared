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
});
