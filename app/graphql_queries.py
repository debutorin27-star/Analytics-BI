AREA_FIELDS = """
fragment AreaFields on Area {
  id
  name
  parentId
}
"""

PAGE_INFO_FIELDS = """
fragment PageInfoFields on PageInfo {
  hasNextPage
  endCursor
  first
}
"""

MANAGER_FIELDS = """
fragment CompanyManagerFields on CompanyManager {
  id
  hhManagerId
  firstName
  middleName
  lastName
  email
  managerRole
  licenseType
  blocked
}
"""

VACANCY_MINI_FIELDS = """
fragment VacancyMiniFields on Vacancy {
  __typename
  ... on VacancyItem {
    id
    title
  }
  ... on VacancyPublicItem {
    id
    title
  }
  ... on VacancyError {
    errorType
    message
  }
}
"""

WORKFLOW_STATUS_MINI_FIELDS = """
fragment WorkflowStatusMiniFields on WorkflowStatus {
  __typename
  ... on WorkflowStatusItem {
    id
    name
    position
    statusType
    vacancy {
      ...VacancyMiniFields
    }
    personCounters {
      all
      unread
    }
  }
  ... on WorkflowStatusPublicItem {
    id
    name
    vacancy {
      ...VacancyMiniFields
    }
  }
  ... on WorkflowStatusError {
    errorType
    message
  }
}
"""

PERSON_CORE_FIELDS = """
fragment PersonCoreFields on PersonItem {
  id
  age
  firstName
  middleName
  lastName
  birthDay
  gender
  updatedAt
  score
  hiddenFields
  updatableWithContacts
  area {
    ...AreaFields
  }
  metroStation {
    id
    name
    parentId
  }
  citizenships {
    items {
      ...AreaFields
    }
  }
  contacts {
    items {
      type
      value
    }
  }
  source {
    id
    name
    type
  }
  tags {
    items {
      id
      name
    }
  }
  files {
    count
    items {
      id
      name
      extension
      size
      createdAt
    }
  }
  photos {
    items {
      id
      size
      url
    }
  }
  resumes {
    items {
      ... on ResumeItem {
        id
        name
        createdAt
        updatedAt
        source {
          type
        }
      }
    }
  }
  responses {
    count
  }
}
"""

PERSON_RESPONSE_FIELDS = """
fragment PersonResponseFields on PersonItem {
  id
  firstName
  middleName
  lastName
  updatedAt
  area {
    id
    name
    parentId
  }
  source {
    id
    name
    type
  }
}
"""

PERSON_LEAN_FIELDS = """
fragment PersonLeanFields on PersonItem {
  id
  age
  firstName
  middleName
  lastName
  birthDay
  gender
  updatedAt
  area {
    id
    name
    parentId
  }
  source {
    id
    name
    type
  }
}
"""

PERSON_HISTORY_FIELDS = """
fragment PersonHistoryFields on PersonItem {
  history(first: $historyFirst) {
    pageInfo {
      ...PageInfoFields
    }
    items {
      __typename
      id
      eventTime
      ... on WorkflowStatusChanged {
        processType
        discardInfo {
          initiator
          reasons
        }
        status {
          id
          name
        }
        vacancy {
          ...VacancyMiniFields
        }
      }
      ... on AttachedToVacancyAndWorkflowStatus {
        status {
          id
          name
        }
        vacancy {
          ...VacancyMiniFields
        }
        vacancyMergeSourceWorkflowStatusSnapshot {
          vacancyId
          vacancyName
          workflowStatusName
        }
      }
      ... on AttachedToVacancy {
        vacancy {
          ...VacancyMiniFields
        }
        vacancyMergeSourceWorkflowStatusSnapshot {
          vacancyId
          vacancyName
          vacancyUrl
          workflowStatusName
        }
      }
      ... on DetachedFromVacancy {
        vacancy {
          ...VacancyMiniFields
        }
      }
    }
  }
}
"""

VACANCIES_QUERY = (
    AREA_FIELDS
    + PAGE_INFO_FIELDS
    + MANAGER_FIELDS
    + """
query Vacancies($after: String, $first: Int!, $filter: VacancyFilterInput) {
  vacancies(after: $after, first: $first, filter: $filter) {
    count
    hasActive
    pageInfo {
      ...PageInfoFields
    }
    items {
      id
      title
      department
      createdAt
      status
      statusUpdatedAt
      proposedDateOfClose
      url
      unreadByOwner
      vacancyLocks
      areas {
        items {
          ...AreaFields
        }
      }
      salary {
        currency
        from
        to
      }
      source {
        type
        href
      }
      hiringPositionCounters {
        planned
        hired
      }
      vacancyManagers {
        items {
          vacancyRole
          manager {
            ...CompanyManagerFields
          }
        }
      }
    }
  }
}
"""
)

VACANCY_DETAILS_QUERY = """
query VacancyDetails($id: Int!) {
  vacancy(id: $id) {
    __typename
    ... on VacancyItem {
      id
      workflowStatuses {
        items {
          id
          name
          position
          statusType
          importFromHhStatuses
          isAutoFilterSource
          personCounters {
            all
            unread
          }
          sla {
            canEdit
            slaDays
          }
        }
      }
      externalVacancies {
        hh {
          count
        }
        avito {
          count
        }
      }
    }
    ... on VacancyError {
      errorType
      message
    }
  }
}
"""

PERSON_SOURCES_QUERY = (
    PAGE_INFO_FIELDS
    + """
query PersonSources($afterCursor: String, $first: Int!, $filterByName: String) {
  personSources(afterCursor: $afterCursor, first: $first, filterByName: $filterByName) {
    pageInfo {
      ...PageInfoFields
    }
    items {
      id
      name
      type
    }
  }
}
"""
)

DICTIONARIES_QUERY = """
query Dictionaries {
  dictionaries {
    areas {
      items {
        id
        name
        parentId
      }
    }
    employments {
      items {
        id
        name
      }
    }
    schedules {
      items {
        id
        name
      }
    }
    languages {
      items {
        id
        name
        parentId
        level {
          id
          name
        }
      }
    }
    industries {
      items {
        id
        name
        parentId
      }
    }
    businessTripReadinesses {
      items {
        id
        name
      }
    }
    travelTimes {
      items {
        id
        name
      }
    }
    relocationTypes {
      items {
        id
        name
      }
    }
    educationLevels {
      items {
        id
        name
      }
    }
    languageLevels {
      items {
        id
        name
      }
    }
  }
}
"""

MANAGERS_QUERY = (
    PAGE_INFO_FIELDS
    + MANAGER_FIELDS
    + """
query Managers($after: String, $first: Int!, $filter: ManagerFilterInput) {
  managers(after: $after, first: $first, filter: $filter) {
    __typename
    ... on Managers {
      pageInfo {
        ...PageInfoFields
      }
      items {
        ...CompanyManagerFields
      }
    }
    ... on ManagersError {
      errorType
      message
    }
  }
}
"""
)


def persons_query(include_history: bool, *, lean: bool = True) -> str:
    history_fragment = PERSON_HISTORY_FIELDS if include_history else ""
    history_spread = "...PersonHistoryFields" if include_history else ""
    history_var = ", $historyFirst: Int!" if include_history else ""
    vacancy_fragment = VACANCY_MINI_FIELDS if include_history else ""
    person_fragment = PERSON_LEAN_FIELDS if lean else PERSON_CORE_FIELDS
    person_spread = "...PersonLeanFields" if lean else "...PersonCoreFields"
    return (
        ("" if lean else AREA_FIELDS)
        + PAGE_INFO_FIELDS
        + vacancy_fragment
        + person_fragment
        + history_fragment
        + f"""
query Persons($after: String, $first: Int!, $filter: PersonFilterInput{history_var}) {{
  persons(after: $after, first: $first, filter: $filter) {{
    pageInfo {{
      ...PageInfoFields
    }}
    items {{
      {person_spread}
      {history_spread}
    }}
  }}
}}
"""
    )


def workflow_status_responses_query(include_history: bool) -> str:
    history_fragment = PERSON_HISTORY_FIELDS if include_history else ""
    history_spread = "...PersonHistoryFields" if include_history else ""
    history_var = ", $historyFirst: Int!" if include_history else ""
    manager_fragment = MANAGER_FIELDS if include_history else ""
    area_fragment = AREA_FIELDS if include_history else ""
    vacancy_fragment = VACANCY_MINI_FIELDS if include_history else ""
    return (
        area_fragment
        + PAGE_INFO_FIELDS
        + manager_fragment
        + vacancy_fragment
        + PERSON_RESPONSE_FIELDS
        + history_fragment
        + f"""
query WorkflowStatusResponses(
  $id: Int!
  $after: String
  $first: Int!
  $filter: ResponseFilterInput
  {history_var}
) {{
  workflowStatus(id: $id) {{
    __typename
    ... on WorkflowStatusItem {{
      id
      responses(after: $after, first: $first, filter: $filter) {{
        pageInfo {{
          ...PageInfoFields
        }}
        items {{
          rating
          unread
          updatedAt
          url
          person {{
            ...PersonResponseFields
            {history_spread}
          }}
        }}
      }}
    }}
    ... on WorkflowStatusError {{
      errorType
      message
    }}
  }}
}}
"""
    )


HIRING_REQUESTS_QUERY = (
    AREA_FIELDS
    + PAGE_INFO_FIELDS
    + VACANCY_MINI_FIELDS
    + """
query HiringRequests($after: String, $first: Int!, $filter: HiringRequestFilterInput) {
  hiringRequests(after: $after, first: $first, filter: $filter) {
    pageInfo {
      ...PageInfoFields
    }
    items {
      id
      name
      department
      description
      status
      creationReason
      createdAt
      approvedAt
      updatedAt
      withdrawnAt
      proposedDateOfClose
      withdrawReason
      withdrawComment
      canEdit
      canRequestApprove
      canWithdraw
      areas {
        items {
          ...AreaFields
        }
      }
      salary {
        currency
        from
        to
      }
      hiringPositionCounters {
        planned
        hired
      }
      managers {
        items {
          __typename
          id
          hhManagerId
          firstName
          middleName
          lastName
          email
          blocked
        }
      }
      customFields {
        items {
          __typename
          id
          name
          required
          ... on HiringRequestSingleLineField {
            text
          }
          ... on HiringRequestMultiLineField {
            text
            outerHint
          }
        }
      }
      vacancy {
        ...VacancyMiniFields
      }
    }
  }
}
"""
)
