/*!
 * Copyright (c) 2024 PLANKA Software GmbH
 * Licensed under the Fair Use License: https://github.com/plankanban/planka/blob/master/LICENSE.md
 */

import { call, join, put, select, spawn, take } from 'redux-saga/effects';

import selectors from '../../selectors';
import entryActions from '../../entry-actions';
import ErrorCodes from '../../constants/ErrorCodes';
import isMem0Embed from '../../utils/is-mem0-embed';
import { notifyMem0ParentAuthExpired } from '../../utils/notify-mem0-parent-path';

let lastRequestTask;

function* queueRequest(method, ...args) {
  if (lastRequestTask) {
    try {
      yield join(lastRequestTask);
    } catch {
      /* empty */
    }
  }

  const accessToken = yield select(selectors.selectAccessToken);

  try {
    return yield call(method, ...args, {
      Authorization: `Bearer ${accessToken}`,
    });
  } catch (error) {
    if (error.code === ErrorCodes.UNAUTHORIZED) {
      if (isMem0Embed()) {
        // O shell OpenMemory renova o JWT e remonta o iframe; nunca mostrar o
        // login nativo do PLANKA para uma pessoa autenticada no shell.
        notifyMem0ParentAuthExpired();
      } else {
        yield put(entryActions.logout(false));
        yield take();
      }
    }

    throw error;
  }
}

export default function* request(method, ...args) {
  lastRequestTask = yield spawn(queueRequest, method, ...args);

  return yield join(lastRequestTask);
}
