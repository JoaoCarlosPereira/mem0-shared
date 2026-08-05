/*!
 * Mem0 Shared — collapsed home groups (Completed / Archived).
 */

import React from 'react';
import PropTypes from 'prop-types';
import classNames from 'classnames';
import { useTranslation } from 'react-i18next';
import { Icon } from 'semantic-ui-react';

import useToggle from '../../../lib/hooks/use-toggle';
import Projects from './Projects';

import styles from './Projects.module.scss';

const CollapsibleProjects = React.memo(
  ({ ids, title, titleIcon, withTypeIndicator, withArchiveButton, defaultExpanded }) => {
    const [t] = useTranslation();
    const [isExpanded, toggleExpanded] = useToggle(defaultExpanded);

    if (!ids || ids.length === 0) {
      return null;
    }

    return (
      <div className={styles.collapsibleWrapper}>
        <button
          type="button"
          className={styles.collapsibleHeader}
          aria-expanded={isExpanded}
          onClick={toggleExpanded}
        >
          <Icon
            name={isExpanded ? 'chevron down' : 'chevron right'}
            className={styles.collapsibleChevron}
          />
          {titleIcon && <Icon name={titleIcon} className={styles.titleIcon} />}
          <span className={styles.collapsibleTitle}>
            {t(title, {
              context: 'title',
            })}
          </span>
          <span className={styles.collapsibleCount}>{ids.length}</span>
        </button>
        <div
          className={classNames(
            styles.collapsibleBody,
            !isExpanded && styles.collapsibleBodyCollapsed,
          )}
        >
          {isExpanded && (
            <Projects
              ids={ids}
              withTypeIndicator={withTypeIndicator}
              withArchiveButton={withArchiveButton}
            />
          )}
        </div>
      </div>
    );
  },
);

CollapsibleProjects.propTypes = {
  ids: PropTypes.array.isRequired, // eslint-disable-line react/forbid-prop-types
  title: PropTypes.string.isRequired,
  titleIcon: PropTypes.string,
  withTypeIndicator: PropTypes.bool,
  withArchiveButton: PropTypes.bool,
  defaultExpanded: PropTypes.bool,
};

CollapsibleProjects.defaultProps = {
  titleIcon: undefined,
  withTypeIndicator: false,
  withArchiveButton: true,
  defaultExpanded: false,
};

export default CollapsibleProjects;
