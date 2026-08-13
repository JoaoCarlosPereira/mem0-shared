export default (groupName) => {
  const normalizedGroupName = String(groupName || '').trim();
  return normalizedGroupName ? `Kanban - ${normalizedGroupName}` : 'Kanban';
};
