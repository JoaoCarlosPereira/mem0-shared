import isMem0Embed from './is-mem0-embed';

describe('isMem0Embed', () => {
  const originalWindow = global.window;

  afterEach(() => {
    global.window = originalWindow;
  });

  test('returns true when embed=1', () => {
    global.window = { location: { search: '?embed=1&token=x' } };
    expect(isMem0Embed()).toBe(true);
  });

  test('returns false when embed is absent', () => {
    global.window = { location: { search: '?token=x' } };
    expect(isMem0Embed()).toBe(false);
  });
});
