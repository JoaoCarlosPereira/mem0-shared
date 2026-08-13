/*!
 * Copyright (c) 2024 PLANKA Software GmbH
 * Licensed under the Fair Use License: https://github.com/plankanban/planka/blob/master/LICENSE.md
 */

/**
 * @swagger
 * /projects/{id}:
 *   get:
 *     summary: Get project details
 *     description: Retrieves comprehensive project information, including boards, board memberships, and other related data.
 *     tags:
 *       - Projects
 *     operationId: getProject
 *     parameters:
 *       - name: id
 *         in: path
 *         required: true
 *         description: ID of the project to retrieve
 *         schema:
 *           type: string
 *           example: "1357158568008091264"
 *     responses:
 *       200:
 *         description: Project details retrieved successfully
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               required:
 *                 - item
 *                 - included
 *               properties:
 *                 item:
 *                   allOf:
 *                     - $ref: '#/components/schemas/Project'
 *                     - type: object
 *                       properties:
 *                         isFavorite:
 *                           type: boolean
 *                           description: Whether the project is marked as favorite by the current user
 *                           example: true
 *                 included:
 *                   type: object
 *                   required:
 *                     - users
 *                     - projectManagers
 *                     - backgroundImages
 *                     - baseCustomFieldGroups
 *                     - boards
 *                     - boardMemberships
 *                     - customFields
 *                     - notificationServices
 *                   properties:
 *                     users:
 *                       type: array
 *                       description: Related users
 *                       items:
 *                         $ref: '#/components/schemas/User'
 *                     projectManagers:
 *                       type: array
 *                       description: Related project managers
 *                       items:
 *                         $ref: '#/components/schemas/ProjectManager'
 *                     backgroundImages:
 *                       type: array
 *                       description: Related background images
 *                       items:
 *                         $ref: '#/components/schemas/BackgroundImage'
 *                     baseCustomFieldGroups:
 *                       type: array
 *                       description: Related base custom field groups
 *                       items:
 *                         $ref: '#/components/schemas/BaseCustomFieldGroup'
 *                     boards:
 *                       type: array
 *                       description: Related boards
 *                       items:
 *                         $ref: '#/components/schemas/Board'
 *                     boardMemberships:
 *                       type: array
 *                       description: Related board memberships (for current user)
 *                       items:
 *                         $ref: '#/components/schemas/BoardMembership'
 *                     customFields:
 *                       type: array
 *                       description: Related custom fields
 *                       items:
 *                         $ref: '#/components/schemas/CustomField'
 *                     notificationServices:
 *                       type: array
 *                       description: Related notification services (for managed projects)
 *                       items:
 *                         $ref: '#/components/schemas/NotificationService'
 *       400:
 *         $ref: '#/components/responses/ValidationError'
 *       401:
 *         $ref: '#/components/responses/Unauthorized'
 *       404:
 *         $ref: '#/components/responses/NotFound'
 */

const { idInput } = require('../../../utils/inputs');
const filterBoardsByGroup = require('../../../utils/filter-boards-by-group');

const Errors = {
  PROJECT_NOT_FOUND: {
    projectNotFound: 'Project not found',
  },
};

module.exports = {
  inputs: {
    id: {
      ...idInput,
      required: true,
    },
  },

  exits: {
    projectNotFound: {
      responseType: 'notFound',
    },
  },

  async fn(inputs) {
    const { currentUser } = this.req;

    const project = await Project.qm.getOneById(inputs.id);

    if (!project) {
      throw Errors.PROJECT_NOT_FOUND;
    }

    const isProjectManager = await sails.helpers.users.isProjectManager(currentUser.id, project.id);

    const boardMemberships = await BoardMembership.qm.getByProjectIdAndUserId(
      project.id,
      currentUser.id,
    );

    let boards;
    if (currentUser.role !== User.Roles.ADMIN || project.ownerProjectManagerId) {
      if (!isProjectManager) {
        if (boardMemberships.length === 0) {
          throw Errors.PROJECT_NOT_FOUND; // Forbidden
        }

        const boardIds = sails.helpers.utils.mapRecords(boardMemberships, 'boardId');
        boards = await Board.qm.getByIds(boardIds);
      }
    }

    if (!boards) {
      boards = await Board.qm.getByProjectId(project.id);
    }

    if (boards.length > 0 && currentUser.email) {
      try {
        const groupResult = await sails.sendNativeQuery(
          `SELECT group_id FROM public.users WHERE lower(email) = lower($1) AND group_id IS NOT NULL LIMIT 1`,
          [currentUser.email],
        );
        if (groupResult.rows.length > 0) {
          const groupId = groupResult.rows[0].group_id;
          const result = await sails.sendNativeQuery(
            `SELECT ua.id, grouped_user.group_id = $1 AS same_group
               FROM planka.user_account AS ua
               JOIN public.users AS grouped_user
                 ON lower(grouped_user.email) = lower(ua.email)
              WHERE grouped_user.group_id IS NOT NULL`,
            [groupId],
          );
          boards = filterBoardsByGroup(
            boards,
            [
              ...result.rows
                .filter(({ same_group: sameGroup }) => sameGroup)
                .map(({ id }) => String(id)),
              currentUser.id,
            ],
            result.rows.map(({ id }) => String(id)),
          );
        }
      } catch (error) {
        sails.log.warn('projects/show: failed to resolve current user group:', error.message);
        boards = [];
      }
    }

    project.isFavorite = await sails.helpers.users.isProjectFavorite(currentUser.id, project.id);

    const projectManagers = await ProjectManager.qm.getByProjectId(project.id);

    const userIds = sails.helpers.utils.mapRecords(projectManagers, 'userId');
    const users = await User.qm.getByIds(userIds);

    const backgroundImages = await BackgroundImage.qm.getByProjectId(project.id);

    const baseCustomFieldGroups = await BaseCustomFieldGroup.qm.getByProjectId(project.id);
    const baseCustomFieldGroupsIds = sails.helpers.utils.mapRecords(baseCustomFieldGroups);

    const customFields =
      await CustomField.qm.getByBaseCustomFieldGroupIds(baseCustomFieldGroupsIds);

    let notificationServices = [];
    if (isProjectManager) {
      boardIds = sails.helpers.utils.mapRecords(boards);
      notificationServices = await NotificationService.qm.getByBoardIds(boardIds);
    }

    return {
      item: project,
      included: {
        projectManagers,
        baseCustomFieldGroups,
        boards,
        boardMemberships,
        customFields,
        notificationServices,
        users: sails.helpers.users.presentMany(users, currentUser),
        backgroundImages: sails.helpers.backgroundImages.presentMany(backgroundImages),
      },
    };
  },
};
