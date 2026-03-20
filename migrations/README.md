# Database Migrations

This directory contains SQL migration scripts for the database schema.

## Running Migrations

### Manual Migration

To run a migration manually, connect to your PostgreSQL database and execute the SQL file:

```bash
psql $DATABASE_URL -f migrations/001_create_generated_tests_table.sql
```

Or if you're already connected to the database:

```sql
\i migrations/001_create_generated_tests_table.sql
```

### Using the API

The API automatically creates all tables defined in the models when it starts up using SQLAlchemy's `Base.metadata.create_all()`. This happens in the `init_db()` function during application startup.

## Migration Files

- `001_create_generated_tests_table.sql` - Creates the `generated_tests` table for storing user's saved AI-generated tests
- `002_create_saved_summaries_table.sql` - Creates the `saved_summaries` table for storing user's saved AI-generated summaries
- `003_update_cat_id_constraint.sql` - Updates the cat_id constraint to allow only cats 0 and 1 (removes black cat option)

## Notes

- The `generated_tests` table is automatically created when the API starts if it doesn't exist
- Manual migrations are provided for reference and for applying changes to existing databases
- Always backup your database before running migrations
