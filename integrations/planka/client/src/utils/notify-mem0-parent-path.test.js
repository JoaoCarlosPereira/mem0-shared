import notifyMem0ParentPath from './notify-mem0-parent-path';

describe('notifyMem0ParentPath', () => {
  const originalWindow = global.window;
  let posted;

  beforeEach(() => {
    posted = [];
    global.window = {
      location: { search: '?embed=1', origin: 'https://memorias.sysmo.com.br' },
      parent: {
        postMessage(data, origin) {
          posted.push({ data, origin });
        },
      },
    };
  });

  afterEach(() => {
    global.window = originalWindow;
  });

  test('posts board path to parent when embed=1', () => {
    notifyMem0ParentPath({
      boardId: '123',
      cardId: null,
      pathname: '/planka/boards/123',
    });
    expect(posted).toHaveLength(1);
    expect(posted[0].data).toEqual({
      source: 'mem0-kanban',
      type: 'path',
      boardId: '123',
      cardId: null,
      pathname: '/planka/boards/123',
    });
    expect(posted[0].origin).toBe('https://memorias.sysmo.com.br');
  });

  test('no-ops when not embed', () => {
    global.window.location.search = '';
    notifyMem0ParentPath({ boardId: '123' });
    expect(posted).toHaveLength(0);
  });
});
