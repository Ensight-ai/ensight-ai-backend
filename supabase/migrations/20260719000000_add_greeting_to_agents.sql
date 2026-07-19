-- Customizable greeting/welcome message shown when the chat widget opens.
-- Null/empty falls back to the widget's built-in default greeting.
alter table agents add column if not exists greeting text;
