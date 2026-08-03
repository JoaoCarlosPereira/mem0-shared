import isMem0Embed, { markMem0Embed } from './is-mem0-embed';

describe('isMem0Embed', () => {
  const originalWindow = global.window;
  const originalSession = global.sessionStorage;

  afterEach(() => {
    global.window = originalWindow;
    global.sessionStorage = originalSession;
  });

  const mockSession = () => {
    const store = {};
    return {
      getItem: (k) => (Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null),
      setItem: (k, v) => {
        store[k] = String(v);
      },
      removeItem: (k) => {
        delete store[k];
      },
    };
  };

  test('returns true when embed=1', () => {
    global.sessionStorage = mockSession();
    global.window = { location: { search: '?embed=1&token=x' } };
    expect(isMem0Embed()).toBe(true);
  });

  test('returns false when embed is absent and no flag', () => {
    global.sessionStorage = mockSession();
    global.window = { location: { search: '?token=x' } };
    expect(isMem0Embed()).toBe(false);
  });

  test('remembers embed via sessionStorage after navigation drops query', () => {
    global.sessionStorage = mockSession();
    global.window = { location: { search: '?embed=1' } };
    expect(isMem0Embed()).toBe(true);
    global.window = { location: { search: '' } };
    expect(isMem0Embed()).toBe(true);
  });

  test('markMem0Embed sets flag', () => {
    global.sessionStorage = mockSession();
    global.window = { location: { search: '' } };
    markMem0Embed();
    expect(isMem0Embed()).toBe(true);
  });
});
