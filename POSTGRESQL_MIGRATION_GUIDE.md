# PostgreSQL Migration Guide

## Overview

The PureMind API has been successfully refactored to use PostgreSQL instead of JSON file storage. This guide covers the migration process, setup, and verification steps.

## What Changed

### New Files Created

**Database Layer** (`/API/database/`):
- `models.py` - SQLAlchemy ORM models for all tables
- `connection.py` - Database session management and connection pooling
- `__init__.py` - Package exports

**Database Managers** (`/API/db_managers/`):
- `user_manager.py` - User account operations
- `auth_manager.py` - Token management
- `profile_manager.py` - Profile, gamification, and streak operations
- `lesson_manager.py` - Lesson and exercise operations
- `store_manager.py` - Store item, inventory, and equipment operations
- `__init__.py` - Package exports

**Migration Script** (`/API/scripts/`):
- `migrate_json_to_postgres.py` - Automated data migration from JSON to PostgreSQL

### Modified Files

- `auth.py` - Now uses database instead of JSON/in-memory storage
- `profiles.py` - Now uses database instead of JSON
- `lessons_manager.py` - Now uses database for lessons, keeps OpenRouter logic
- `async_managers.py` - Updated to use database for token cleanup and lesson lookups
- `main.py` - Initializes database on startup
- `requirements.txt` - Added SQLAlchemy, psycopg2, and alembic

## Database Schema

### Tables

**User Management:**
- `users` - User accounts and authentication
- `auth_tokens` - Session tokens with expiration

**Profiles & Gamification:**
- `profiles` - User profiles with XP, meowcoins, and streak tracking
- `completed_exercises` - Track exercise completions and rewards
- `courses` - Normalized course data
- `lessons` - Lesson content with YouTube links
- `exercises` - Quiz exercises (can be generated dynamically)

**Store System:**
- `store_items` - Available cat accessories
- `inventory` - User-owned items
- `equipped_items` - Currently equipped accessories

## Prerequisites

1. **PostgreSQL 12+** installed and running
2. **Python 3.8+**
3. **All dependencies installed**: `pip install -r requirements.txt`

## Setup Instructions

### 1. Install PostgreSQL

```bash
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# macOS
brew install postgresql

# Start PostgreSQL service
sudo systemctl start postgresql
# or
brew services start postgresql
```

### 2. Create Database User and Database

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create user (enter password when prompted)
CREATE USER lessons_user WITH PASSWORD 'secure_password_here';

# Create database
CREATE DATABASE lessons_db;

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE lessons_db TO lessons_user;

# Exit psql
\q
```

### 3. Configure Environment Variables

Create or update `.env` file in `/API/` directory:

```env
# Database Configuration
DATABASE_URL=postgresql://lessons_user:secure_password_here@localhost:5432/lessons_db

# Connection Pooling
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# OpenRouter (existing)
OPENROUTER_API_KEY=your_api_key_here

# Other existing variables...
```

### 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 5. Run Migration Script

The migration script will:
- Backup existing JSON files to `/API/backups/json_backup_*/`
- Create all database tables
- Migrate all data from JSON files to PostgreSQL
- Insert store items
- Verify data integrity

**Run the migration:**

```bash
cd /API
python scripts/migrate_json_to_postgres.py
```

**Expected output:**
```
Starting PostgreSQL migration...
Backing up JSON files...
Backed up users.json
Backed up profiles.json
Backed up lessons.json
Database initialized successfully
Migrating users...
Migrated 1 users
Migrating lessons and courses...
Migrated 1000+ lessons into 20+ courses
Inserting store items...
Migrating profiles...
Migrated 1 profiles
Verifying migration...
Migration Summary:
  users: 1
  profiles: 1
  courses: 20+
  lessons: 1000+
  store_items: 4
  completed_exercises: 10+
  inventory_items: 5+
Migration completed successfully!
```

## Running the API

### Start the API Server

```bash
cd /API
python main.py
```

Or with uvicorn directly:

```bash
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

The API will:
1. Initialize the database (create tables if they don't exist)
2. Check database connectivity
3. Start token cleanup background task
4. Begin accepting requests

### Test the API

```bash
# Health check
curl http://localhost:5000/health

# API overview
curl http://localhost:5000/

# Register new user
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass123","email":"test@example.com"}'

# Login
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass123"}'

# List lessons
curl http://localhost:5000/api/lessons

# Search lessons
curl "http://localhost:5000/api/lessons/search?q=historia"
```

## Verification Checklist

After migration, verify the following:

- [ ] Database tables created successfully
- [ ] All users migrated (same count as users.json)
- [ ] All profiles migrated (same count as profiles.json)
- [ ] All lessons migrated (same count as lessons.json)
- [ ] All store items present (4 items: sunglasses, cap, moustache, butterfly)
- [ ] User login/logout works correctly
- [ ] Profile creation and updates work
- [ ] Lesson queries return correct data
- [ ] Exercise completion updates gamification data
- [ ] Leaderboard returns correct rankings
- [ ] Store operations work (purchase, equip, unequip)
- [ ] API response times are acceptable (<500ms)

## Data Integrity Notes

### What's Preserved
- All user credentials (password hashes)
- All profile data (name, about, cat_id, illness_id)
- XP and meowcoins balances
- Streak tracking data
- Completed exercises history
- User inventory
- Equipped items

### What's New in Database
- Primary key auto-increment IDs (for better performance)
- Foreign key relationships with cascading deletes
- Indexes on frequently queried columns (user_id, lesson_id, xp, meowcoins, streak)
- CHECK constraints for data validation
- JSONB field for exercise options
- Timestamp tracking (created_at, updated_at)

### Migration Tracking
- ID mappings maintained during migration (old_id → new_id)
- Foreign key references automatically resolved
- Empty/null values handled appropriately

## Performance Optimizations

The database includes several optimizations:

1. **Connection Pooling** - Maintains pool of persistent connections
2. **Indexes** - On foreign keys, leaderboard columns, and search fields
3. **Eager Loading** - Related data loaded efficiently via relationships
4. **Full-Text Search** - GIN index on lesson titles for fast searching
5. **Query Optimization** - Database handles sorting/filtering efficiently

## Troubleshooting

### Database Connection Failed

```python
# Check connectivity
from database import check_db_connection
check_db_connection()

# Verify DATABASE_URL in .env
echo $DATABASE_URL
```

### Tables Not Created

```bash
# Manually initialize database
python -c "from database import init_db; init_db()"
```

### Migration Failed

1. Check the backup was created: `ls -la /API/backups/`
2. Verify PostgreSQL is running: `sudo systemctl status postgresql`
3. Check DATABASE_URL is correct: `cat .env | grep DATABASE_URL`
4. Review migration logs: `python scripts/migrate_json_to_postgres.py 2>&1 | tee migration.log`

### Rollback JSON Files

If something goes wrong, restore from backup:

```bash
# Find backup directory
ls -la /API/backups/json_backup_*/

# Restore files
cp /API/backups/json_backup_TIMESTAMP/* /API/
```

## Security Considerations

1. **Password Hashes** - Currently using SHA-256 (upgrade to bcrypt/argon2 recommended)
2. **Token Expiration** - Tokens expire after 30 days
3. **Database User** - Use limited privileges for production
4. **Connection Pooling** - Includes pool_pre_ping for connection validation
5. **SQL Injection** - ORM provides automatic parameterization

## Next Steps for Production

1. Upgrade password hashing algorithm (bcrypt/argon2)
2. Implement read replicas for scaling
3. Add database monitoring and backups
4. Configure connection pooling for expected load
5. Add caching layer (Redis) for frequently accessed data
6. Implement database migrations (Alembic)
7. Add comprehensive logging and monitoring

## API Changes Summary

### Backwards Compatible
All API endpoints maintain the same interface - no changes to request/response formats.

### Internal Changes
- `auth.py` - Now uses database instead of in-memory storage
- `profiles.py` - Now uses database instead of JSON
- `lessons_manager.py` - Now uses database for lesson lookups
- Token management moved from in-memory to database

### No Changes Required
- Router endpoints remain identical
- Request/response formats unchanged
- OpenRouter API integration unchanged
- Speech services unchanged

## Support & Debugging

Enable database query logging:

```python
# In database/connection.py, set echo=True
engine = create_engine(
    DATABASE_URL,
    echo=True,  # Enable SQL logging
    ...
)
```

Check logs for issues:
```bash
# API logs
tail -f /var/log/lessons-api.log

# PostgreSQL logs
tail -f /var/log/postgresql/postgresql.log
```

---

**Migration Date**: 2026-03-07
**Database Version**: PostgreSQL 12+
**Python Version**: 3.8+
**SQLAlchemy Version**: 2.0.25
