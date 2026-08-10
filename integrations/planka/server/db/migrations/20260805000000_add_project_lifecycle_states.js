/*!
 * Copyright (c) 2024 PLANKA Software GmbH
 * Licensed under the Fair Use License: https://github.com/plankanban/planka/blob/master/LICENSE.md
 */

// The lifecycle columns are created by the preceding migration
// `20260804000000_add_project_archive_and_completed.js`.
// This migration is kept as a no-op because older deployments may already
// have recorded it under this filename before the duplicate was removed.
module.exports.up = async () => {};

module.exports.down = async () => {};
