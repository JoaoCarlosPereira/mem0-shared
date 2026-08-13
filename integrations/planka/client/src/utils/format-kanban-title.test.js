import formatKanbanTitle from './format-kanban-title';

describe('formatKanbanTitle', () => {
  test('includes the current group name', () => {
    expect(formatKanbanTitle('Fiscal')).toBe('Kanban - Fiscal');
  });

  test('falls back to Kanban without a group', () => {
    expect(formatKanbanTitle(null)).toBe('Kanban');
    expect(formatKanbanTitle('  ')).toBe('Kanban');
  });
});
