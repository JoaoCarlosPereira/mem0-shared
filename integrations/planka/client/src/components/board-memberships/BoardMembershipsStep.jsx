/*!
 * Copyright (c) 2024 PLANKA Software GmbH
 * Licensed under the Fair Use License: https://github.com/plankanban/planka/blob/master/LICENSE.md
 */

import React from 'react';
import PropTypes from 'prop-types';
import { useSelector } from 'react-redux';

import selectors from '../../selectors';
import PureBoardMembershipsStep from './PureBoardMembershipsStep';

const BoardMembershipsStep = React.memo(
  ({
    currentUserIds,
    title,
    clearButtonContent,
    onUserSelect,
    onUserDeselect,
    onClear,
    onBack,
    activeOnly,
  }) => {
    const boardMemberships = useSelector(selectors.selectMembershipsForCurrentBoard);
    const activeMemberUserIds = useSelector(selectors.selectActiveMemberUserIdsForCurrentBoard);
    const items = activeOnly
      ? boardMemberships.filter(({ user }) => activeMemberUserIds.includes(user.id))
      : boardMemberships;

    return (
      <PureBoardMembershipsStep
        items={items}
        currentUserIds={currentUserIds}
        title={title}
        clearButtonContent={clearButtonContent}
        onUserSelect={onUserSelect}
        onUserDeselect={onUserDeselect}
        onClear={onClear}
        onBack={onBack}
      />
    );
  },
);

BoardMembershipsStep.propTypes = {
  currentUserIds: PropTypes.array.isRequired, // eslint-disable-line react/forbid-prop-types
  title: PropTypes.string,
  clearButtonContent: PropTypes.string,
  onUserSelect: PropTypes.func.isRequired,
  onUserDeselect: PropTypes.func.isRequired,
  onClear: PropTypes.func,
  onBack: PropTypes.func,
  activeOnly: PropTypes.bool,
};

BoardMembershipsStep.defaultProps = {
  title: undefined,
  clearButtonContent: undefined,
  onClear: undefined,
  onBack: undefined,
  activeOnly: false,
};

export default BoardMembershipsStep;
