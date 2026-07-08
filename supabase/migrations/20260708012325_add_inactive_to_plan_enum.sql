-- add_inactive_to_plan_enum
-- New accounts start on the "inactive" plan (hard paywall) until they pay.
-- The plan column is a Postgres enum, so the value must exist before we can
-- insert it.

alter type plan add value if not exists 'inactive';
