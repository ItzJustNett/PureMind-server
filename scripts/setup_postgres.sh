#!/bin/bash

# PostgreSQL Setup Script
# Automates PostgreSQL database and user creation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}PostgreSQL Setup Script${NC}"
echo "======================"

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo -e "${RED}PostgreSQL is not installed${NC}"
    echo "Install PostgreSQL first:"
    echo "  Ubuntu/Debian: sudo apt-get install postgresql postgresql-contrib"
    echo "  macOS: brew install postgresql"
    exit 1
fi

# Check if PostgreSQL service is running
if ! pg_isready -h localhost &> /dev/null; then
    echo -e "${RED}PostgreSQL service is not running${NC}"
    echo "Start PostgreSQL:"
    echo "  Linux: sudo systemctl start postgresql"
    echo "  macOS: brew services start postgresql"
    exit 1
fi

echo -e "${GREEN}✓ PostgreSQL is installed and running${NC}"

# Prompt for database name
read -p "Enter database name (default: lessons_db): " DB_NAME
DB_NAME=${DB_NAME:-lessons_db}

# Prompt for user name
read -p "Enter database username (default: lessons_user): " DB_USER
DB_USER=${DB_USER:-lessons_user}

# Prompt for password
read -sp "Enter password for $DB_USER: " DB_PASS
echo ""
read -sp "Confirm password: " DB_PASS_CONFIRM
echo ""

if [ "$DB_PASS" != "$DB_PASS_CONFIRM" ]; then
    echo -e "${RED}Passwords do not match${NC}"
    exit 1
fi

# Create database and user
echo -e "${YELLOW}Creating database and user...${NC}"

sudo -u postgres psql << EOF
-- Create user
CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';

-- Create database
CREATE DATABASE $DB_NAME;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;

-- Exit
\q
EOF

echo -e "${GREEN}✓ Database and user created${NC}"

# Create .env file if it doesn't exist
ENV_FILE="$(dirname "$0")/../.env"

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    cat > "$ENV_FILE" << EOF
# Database Configuration
DATABASE_URL=postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME

# Connection Pooling
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# OpenRouter API
OPENROUTER_API_KEY=

# Port
PORT=5000
EOF
    echo -e "${GREEN}✓ .env file created${NC}"
    echo "  Don't forget to add your OPENROUTER_API_KEY"
else
    echo -e "${YELLOW}Updating .env file...${NC}"
    # Update DATABASE_URL if it exists, otherwise add it
    if grep -q "DATABASE_URL=" "$ENV_FILE"; then
        sed -i "s|DATABASE_URL=.*|DATABASE_URL=postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME|" "$ENV_FILE"
    else
        echo "DATABASE_URL=postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME" >> "$ENV_FILE"
    fi
    echo -e "${GREEN}✓ .env file updated${NC}"
fi

# Install Python dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip install -r "$(dirname "$0")/../requirements.txt" > /dev/null 2>&1
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Run migration
echo -e "${YELLOW}Running data migration...${NC}"
python "$(dirname "$0")/migrate_json_to_postgres.py"

echo ""
echo -e "${GREEN}Setup completed successfully!${NC}"
echo ""
echo "Next steps:"
echo "  1. Review the .env file: cat $(dirname "$0")/../.env"
echo "  2. Start the API: python $(dirname "$0")/../main.py"
echo "  3. Test the API: curl http://localhost:5000/health"
echo ""
echo "For more details, see: $(dirname "$0")/../POSTGRESQL_MIGRATION_GUIDE.md"
