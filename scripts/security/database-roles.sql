-- Run manually as the migration owner on Neon production, AFTER migrations.
-- Do not give the running APIs owner credentials. Set passwords using psql \password.
BEGIN;
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'shopdesk_app') THEN
    CREATE ROLE shopdesk_app LOGIN NOINHERIT NOCREATEDB NOCREATEROLE;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'shopdesk_backup') THEN
    CREATE ROLE shopdesk_backup LOGIN NOINHERIT NOCREATEDB NOCREATEROLE;
  END IF;
END $$;
DO $$ BEGIN
  IF EXISTS (SELECT FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member
             WHERE r.rolname IN ('shopdesk_app', 'shopdesk_backup')) THEN
    RAISE EXCEPTION 'Restricted roles must not be members of another role; remove memberships first';
  END IF;
  IF EXISTS (SELECT FROM pg_roles WHERE rolname IN ('shopdesk_app', 'shopdesk_backup')
             AND (rolsuper OR rolcreaterole OR rolcreatedb OR rolbypassrls))
     OR EXISTS (SELECT FROM pg_class c JOIN pg_roles r ON r.oid = c.relowner
                WHERE r.rolname IN ('shopdesk_app', 'shopdesk_backup')) THEN
    RAISE EXCEPTION 'Runtime/backup roles must not be privileged or own database objects';
  END IF;
END $$;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM shopdesk_app, shopdesk_backup;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM shopdesk_app, shopdesk_backup;
REVOKE DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON public.audit_logs FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO shopdesk_app, shopdesk_backup;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO shopdesk_app;
REVOKE UPDATE ON public.audit_logs FROM shopdesk_app;
REVOKE ALL ON public.alembic_version FROM shopdesk_app;
GRANT SELECT ON public.alembic_version TO shopdesk_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO shopdesk_app;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO shopdesk_backup;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO shopdesk_backup;
-- Applies to future objects created by the SAME owner running this file.
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE ON TABLES TO shopdesk_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO shopdesk_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO shopdesk_backup;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO shopdesk_backup;
COMMIT;
-- Re-run after migrations to reapply exceptions. Check membership too: neither role may
-- inherit an owner or neon_superuser role. See MANUAL_DEPLOYMENT.md verification queries.
