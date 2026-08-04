const assert = require('assert');
const { describe, it } = require('node:test');

global.Card = {
  Types: {
    PROJECT: 'project',
    STORY: 'story',
  },
};

const createController = require('../../api/controllers/cards/create');
const updateController = require('../../api/controllers/cards/update');

describe('card description length', () => {
  it('does not impose an application maxLength on create or update', () => {
    assert.strictEqual(createController.inputs.description.maxLength, undefined);
    assert.strictEqual(updateController.inputs.description.maxLength, undefined);
  });
});
