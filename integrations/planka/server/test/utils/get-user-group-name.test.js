const assert = require('assert');

const getUserGroupName = require('../../utils/get-user-group-name');

describe('getUserGroupName', () => {
  it('returns the group name for the authenticated email', async () => {
    const query = async (_sql, values) => {
      assert.deepStrictEqual(values, ['user@example.com']);
      return { rows: [{ name: 'Fiscal' }] };
    };

    assert.strictEqual(await getUserGroupName(query, 'user@example.com'), 'Fiscal');
  });

  it('returns null when the user has no group', async () => {
    const query = async () => ({ rows: [] });

    assert.strictEqual(await getUserGroupName(query, 'user@example.com'), null);
  });
});
