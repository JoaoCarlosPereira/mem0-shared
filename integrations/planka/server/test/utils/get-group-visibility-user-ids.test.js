const assert = require('assert');

const getGroupVisibilityUserIds = require('../../utils/get-group-visibility-user-ids');

describe('getGroupVisibilityUserIds', () => {
  it('uses the authenticated JWT group when the Planka email has no public user', async () => {
    const calls = [];
    const query = async (sql, values) => {
      calls.push({ sql, values });
      return { rows: [] };
    };

    const result = await getGroupVisibilityUserIds(
      query,
      { email: 'ui-user@mem0.local' },
      'default-group-id',
    );

    assert.strictEqual(result.currentGroupId, 'default-group-id');
    assert.strictEqual(calls.length, 1);
    assert.deepStrictEqual(calls[0].values, ['default-group-id']);
  });

  it('falls back to the public user group when JWT has no group claim', async () => {
    const query = async (sql) => {
      if (sql.includes('FROM public.users')) {
        return { rows: [{ group_id: 'database-group-id' }] };
      }
      return { rows: [] };
    };

    const result = await getGroupVisibilityUserIds(query, {
      email: 'person@example.com',
    });

    assert.strictEqual(result.currentGroupId, 'database-group-id');
  });
});
