const assert = require('assert');
const { describe, it } = require('node:test');

const getActiveMemberUserIds = require('../../api/helpers/boards/get-active-member-user-ids');

global._ = {
  uniq(values) {
    return [...new Set(values)];
  },
};

describe('get-active-member-user-ids', () => {
  it('returns users who interacted with cards through supported activity types', () => {
    const result = getActiveMemberUserIds({
      cards: [{ creatorUserId: 'creator-1' }],
      cardMemberships: [{ userId: 'member-1' }],
      comments: [{ userId: 'commenter-1' }],
      actions: [{ userId: 'actor-1' }],
      attachments: [{ creatorUserId: 'attachment-1' }],
      tasks: [{ assigneeUserId: 'assignee-1' }],
    });

    assert.deepStrictEqual(result, [
      'creator-1',
      'member-1',
      'commenter-1',
      'actor-1',
      'attachment-1',
      'assignee-1',
    ]);
  });

  it('removes duplicates and ignores missing actors', () => {
    const result = getActiveMemberUserIds({
      cards: [{ creatorUserId: 'user-1' }, { creatorUserId: 'user-1' }, { creatorUserId: null }],
      cardMemberships: [{ userId: 'user-1' }, { userId: undefined }],
      comments: [],
      actions: [],
      attachments: [],
      tasks: [],
    });

    assert.deepStrictEqual(result, ['user-1']);
  });
});
