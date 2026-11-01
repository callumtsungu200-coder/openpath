-- GOV.UK Find an apprenticeship. One source lists many employers, so employer details
-- belong on each opportunity rather than on the source.
alter type source_adapter add value if not exists 'gov_apprenticeships';
alter table opportunities add column if not exists company_url text;
alter table opportunities add column if not exists company_description text;
