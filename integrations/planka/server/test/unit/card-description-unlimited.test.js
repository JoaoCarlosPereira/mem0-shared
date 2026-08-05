const assert = require('assert');
const fs = require('fs');
const path = require('path');
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

describe('Mem0 Socket.IO configuration', () => {
  it('uses stable same-origin polling with session bypass', () => {
    const socketSource = fs.readFileSync(
      path.resolve(__dirname, '../../../client/src/api/socket.js'),
      'utf8',
    );

    assert.match(socketSource, /io\.sails\.url = window\.location\.origin/);
    assert.match(socketSource, /io\.sails\.query = 'nosession=1'/);
    assert.match(socketSource, /io\.sails\.transports = \['polling'\]/);
  });
});
