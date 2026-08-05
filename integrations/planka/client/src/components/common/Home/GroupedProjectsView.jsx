/*!
 * Copyright (c) 2024 PLANKA Software GmbH
 * Licensed under the Fair Use License: https://github.com/plankanban/planka/blob/master/LICENSE.md
 */

import React, { useCallback } from 'react';
import { useDispatch, useSelector } from 'react-redux';

import selectors from '../../../selectors';
import entryActions from '../../../entry-actions';
import { isUserAdminOrProjectOwner } from '../../../utils/record-helpers';
import { ProjectGroups, ProjectTypes } from '../../../constants/Enums';
import { ProjectGroupIcons } from '../../../constants/Icons';
import Projects from './Projects';
import CollapsibleProjects from './CollapsibleProjects';

const TITLE_BY_GROUP = {
  [ProjectGroups.MY_OWN]: 'common.myOwn',
  [ProjectGroups.TEAM]: 'common.team',
  [ProjectGroups.SHARED_WITH_ME]: 'common.sharedWithMe',
  [ProjectGroups.OTHERS]: 'common.others',
};

// Mem0 Shared: only team (Equipe) projects — hide personal "Meus" create/section.
const DEFAULT_TYPE_BY_GROUP = {
  [ProjectGroups.TEAM]: ProjectTypes.SHARED,
};

const GroupedProjectsView = React.memo(() => {
  const projectIdsByGroup = useSelector(selectors.selectFilteredProjctIdsByGroupForCurrentUser);

  const canAdd = useSelector((state) => {
    const user = selectors.selectCurrentUser(state);
    return isUserAdminOrProjectOwner(user);
  });

  const dispatch = useDispatch();

  const handleAdd = useCallback(
    (defaultType) => {
      dispatch(entryActions.openAddProjectModal(defaultType));
    },
    [dispatch],
  );

  return (
    <>
      {(projectIdsByGroup.teamActiveIds.length > 0 || canAdd) && (
        <Projects
          ids={projectIdsByGroup.teamActiveIds}
          title={TITLE_BY_GROUP[ProjectGroups.TEAM]}
          titleIcon={ProjectGroupIcons[ProjectGroups.TEAM]}
          withArchiveButton
          onAdd={() => handleAdd(DEFAULT_TYPE_BY_GROUP[ProjectGroups.TEAM])}
        />
      )}
      {/* Mem0 Shared: kanban-archive-lifecycle — grupos recolhidos por padrão
       * (CollapsibleProjects.defaultExpanded === false); não removem o quadro
       * da equipe, só o tiram da lista principal. */}
      <CollapsibleProjects
        ids={projectIdsByGroup.teamCompletedIds}
        title="common.completed"
        titleIcon="check circle outline"
        withArchiveButton
      />
      <CollapsibleProjects
        ids={projectIdsByGroup.teamArchivedIds}
        title="common.archived"
        titleIcon="archive"
        withArchiveButton
      />
      {[ProjectGroups.SHARED_WITH_ME, ProjectGroups.OTHERS].map(
        (group) =>
          projectIdsByGroup[group].length > 0 && (
            <Projects
              withTypeIndicator
              key={group}
              ids={projectIdsByGroup[group]}
              title={TITLE_BY_GROUP[group]}
              titleIcon={ProjectGroupIcons[group]}
            />
          ),
      )}
    </>
  );
});

export default GroupedProjectsView;
