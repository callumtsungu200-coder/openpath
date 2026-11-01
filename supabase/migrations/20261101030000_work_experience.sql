-- Work experience sources. Recurring programmes keep their page between rounds, so whether
-- applications are open is its own fact: null means the source does not say.
alter type source_adapter add value if not exists 'springpod';
alter type source_adapter add value if not exists 'futures_finder';
alter type source_adapter add value if not exists 'programme_pages';
alter table opportunities add column if not exists application_status text
  check (application_status in ('open', 'closed'));
