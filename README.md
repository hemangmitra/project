# Task Management API

A comprehensive FastAPI-based task management system with JWT authentication, audit trails, and admin features.

## Features

- **JWT Authentication**: Access tokens (15 min) + refresh tokens (7 days) with rotation
- **User Management**: Registration, profile management, role-based access
- **Task Management**: CRUD operations with filtering, search, and pagination
- **Audit Trail**: Complete audit logging for all operations
- **Admin Features**: User management, bulk operations, system statistics
- **Security**: BCrypt passwords, HTTP-only cookies, CORS protection

## Tech Stack

- **FastAPI**: Modern, fast web framework
- **SQLAlchemy**: SQL toolkit and ORM
- **PostgreSQL**: Primary database
- **Alembic**: Database migrations
- **Pydantic**: Data validation
- **JWT**: Token-based authentication
- **BCrypt**: Password hashing

## Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd task-management-api
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up PostgreSQL database**
```bash
createdb taskmanager
```

5. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your database credentials
```

6. **Run migrations**
```bash
alembic upgrade head
```

7. **Start the server**
```bash
python app/main.py
```

The API will be available at `http://localhost:8001`

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`

## Authentication

The API uses JWT tokens for authentication:

1. **Register**: `POST /api/auth/register`
2. **Login**: `POST /api/auth/login`
3. **Refresh**: `POST /api/auth/refresh`
4. **Logout**: `POST /api/auth/logout`

## API Endpoints

### Authentication (`/api/auth/`)
- `POST /register` - Register new user
- `POST /login` - User login
- `POST /refresh` - Refresh access token
- `POST /logout` - User logout
- `POST /revoke-token` - Revoke refresh token

### Users (`/api/users/`)
- `GET /me` - Get current user profile
- `PUT /me` - Update current user profile
- `GET /` - List all users (admin only)
- `GET /{user_id}` - Get user by ID (admin only)
- `GET /{user_id}/refresh-tokens` - View user's tokens (admin only)

### Tasks (`/api/tasks/`)
- `POST /` - Create new task
- `GET /` - List tasks with filtering
- `GET /{task_id}` - Get task details
- `PUT /{task_id}` - Update task
- `DELETE /{task_id}` - Delete task
- `POST /{task_id}/assign` - Assign task (admin only)
- `GET /assigned/{user_id}` - Get user's assigned tasks (admin only)

### Admin (`/api/admin/`)
- `GET /audit-logs` - View audit trail
- `GET /system-stats` - System statistics
- `POST /bulk-assign` - Bulk task assignment
- `GET /user-activity/{user_id}` - User activity summary

## Database Schema

### Users
- id, email, username, hashed_password
- role (admin/user), is_active
- created_at, updated_at

### Tasks
- id, title, description, status, priority
- due_date, assigned_user_id, created_by
- created_at, updated_at, is_deleted

### Refresh Tokens
- id, token, user_id, expires_at
- is_revoked, created_at, replaced_by_token

### Audit Logs
- id, user_id, task_id, action
- old_values, new_values, timestamp

## Security Features

- Password hashing with BCrypt
- JWT tokens with expiration
- HTTP-only cookies for refresh tokens
- Token rotation on refresh
- CORS protection
- Input validation with Pydantic
- SQL injection prevention
- Role-based access control

## Development

### Database Migrations

Create a new migration:
```bash
alembic revision --autogenerate -m "Description"
```

Apply migrations:
```bash
alembic upgrade head
```

### Testing

Run the application:
```bash
python app/main.py
```

## Configuration

Environment variables in `.env`:

```
DATABASE_URL=postgresql://username:password@localhost:5432/taskmanager
JWT_SECRET_KEY=your-super-secret-jwt-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
CORS_ORIGINS=["http://localhost:3000"]
DEBUG=True
```