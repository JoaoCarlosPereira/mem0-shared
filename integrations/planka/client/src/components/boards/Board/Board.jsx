/*!
 * Copyright (c) 2024 PLANKA Software GmbH
 * Licensed under the Fair Use License: https://github.com/plankanban/planka/blob/master/LICENSE.md
 */

import React from 'react';
import { useSelector } from 'react-redux';

import selectors from '../../../selectors';
import ModalTypes from '../../../constants/ModalTypes';
import { BoardContexts, BoardViews } from '../../../constants/Enums';
import KanbanContent from './KanbanContent';
import FiniteContent from './FiniteContent';
import EndlessContent from './EndlessContent';
import ShortcutsProvider from './ShortcutsProvider';
import CardModal from '../../cards/CardModal';
import BoardActivitiesModal from '../../activities/BoardActivitiesModal';

const Board = React.memo(() => {
  const board = useSelector(selectors.selectCurrentBoard);
  const modal = useSelector(selectors.selectCurrentModal);
  const isCardModalOpened = useSelector((state) => !!selectors.selectPath(state).cardId);

  let Content;
  // Archive/Trash are list/grid contexts — never keep Kanban columns when
  // switching via "Ações do quadro → Arquivar/Lixeira" (Mem0: was a no-op
  // while view stayed on kanban).
  if (
    board.context === BoardContexts.ARCHIVE ||
    board.context === BoardContexts.TRASH
  ) {
    Content = EndlessContent;
  } else if (board.view === BoardViews.KANBAN) {
    Content = KanbanContent;
  } else {
    Content = FiniteContent;
  }

  let modalNode = null;
  if (isCardModalOpened) {
    modalNode = <CardModal />;
  } else if (modal) {
    switch (modal.type) {
      case ModalTypes.BOARD_ACTIVITIES:
        modalNode = <BoardActivitiesModal />;

        break;
      default:
    }
  }

  return (
    <>
      <ShortcutsProvider>
        <Content />
      </ShortcutsProvider>
      {modalNode}
    </>
  );
});

export default Board;
