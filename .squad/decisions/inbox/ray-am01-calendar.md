# Ray AM-01 Academic Calendar

- Date: 2026-05-09
- Author: Ray

## Context

AM-01 needed family-scoped academic planning with school years, terms, grading periods, holidays, and an instructional day counter that would not drift across timezones.

## Decision

- Store academic planning boundaries and calendar events as `date` values rather than datetimes.
- Calculate instructional days from weekday defaults across the school year, then apply explicit calendar-event overrides so weekday holidays remove days and custom weekend makeup days add them back.
- Keep calendar management under the existing curriculum RBAC surface: parent/co-parent/tutor can manage, while student viewers remain read-only through calendar GET endpoints.

## Impact

- The API and frontend can safely exchange `YYYY-MM-DD` values without local/UTC rollover bugs.
- Families can model standard school calendars plus exceptions like closures and Saturday instructional days with predictable day counts.
