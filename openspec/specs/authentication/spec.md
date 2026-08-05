# Authentication and Authorization System

## Overview
Role-based access control system for Telegram bot with admin and regular user roles.

## Core Components

### Authorization Manager
- **Purpose**: Control access to bot features
- **Storage**: PostgreSQL database
- **Methods**:
  - Whitelist-based authorization
  - Admin role management
  - Session tracking

### User Roles

#### Regular Users
- **Access**: Basic bot commands
- **Features**:
  - Content analysis
  - RAG queries
  - Personal statistics
  - Export functionality

#### Administrators
- **Access**: All user features + admin panel
- **Additional Features**:
  - User management
  - Access control
  - System configuration
  - Monitoring dashboard

## Authorization Flow

```
User sends command
    ↓
Check authorization status
    ↓
┌─────────────────┐
│ Is authorized?  │
└────────┬────────┘
         │
    ┌────┴────┐
    ↓         ↓
  Yes        No
    │         │
    ↓         ↓
Execute    Send "Access Denied"
command    message with contact info
```

## Configuration

### Enable/Disable Authorization
```python
ENABLE_USER_AUTHORIZATION = True  # Master switch
```

### Allowed Users List
```python
ALLOWED_USERS = [
    425447101,  # User ID 1
    # Add more user IDs as needed
]
```

### Admin Users List
```python
ADMIN_USERS = [
    425447101,  # Admin ID 1
    # Add more admin IDs as needed
]
```

### Unauthorized Message
```python
UNAUTHORIZED_MESSAGE = """🚫 **Доступ запрещен**

К сожалению, вы не авторизованы для использования этого бота.

Для получения доступа обратитесь к администратору."""
```

## Admin Commands

### User Management
- `/add_user <user_id>` - Grant access to user
- `/remove_user <user_id>` - Revoke user access
- `/users` - List all authorized users
- `/user_info <user_id>` - Get user details

### System Management
- `/admin` - Access admin panel
- `/auth_status` - Check system authorization status

## Security Features

### Input Validation
- User ID format validation
- SQL injection prevention
- Rate limiting for admin actions

### Audit Logging
- All admin actions logged
- User access attempts tracked
- Failed authorization attempts recorded

### Data Protection
- No sensitive data in logs
- Secure credential storage
- Environment variable usage

## Technical Implementation

### Decorators
```python
@require_authorization
async def protected_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only accessible to authorized users
    pass
```

### Middleware Pattern
- Pre-command authorization check
- Post-command audit logging
- Error handling for unauthorized access

## Database Schema

### Users Table
```sql
CREATE TABLE users (
  id BIGINT PRIMARY KEY,
  username VARCHAR(255),
  first_name VARCHAR(255),
  last_name VARCHAR(255),
  is_authorized BOOLEAN DEFAULT FALSE,
  is_admin BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_active TIMESTAMP,
  access_count INTEGER DEFAULT 0
);
```

### Authorization Log
```sql
CREATE TABLE auth_logs (
  id SERIAL PRIMARY KEY,
  user_id BIGINT,
  command VARCHAR(100),
  authorized BOOLEAN,
  attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  ip_address VARCHAR(45)
);
```

## Error Handling

### Unauthorized Access
- Friendly denial message
- Contact information for admin
- Rate limiting for repeated attempts

### Admin Errors
- Permission denied messages
- Invalid user ID handling
- Database connection failures

## Monitoring
- Authorization success/failure rates
- Admin action audit trail
- User activity metrics
- Security incident alerts