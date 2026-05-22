-- Nexus User Management System - Database Initialization
-- This script runs automatically when PostgreSQL container starts

-- Create schemas for different bounded contexts
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS users;
CREATE SCHEMA IF NOT EXISTS roles;

-- ============================================
-- Auth Schema - Authentication & Sessions
-- ============================================

CREATE TABLE IF NOT EXISTS auth.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    last_login_at TIMESTAMP WITH TIME ZONE,
    failed_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS auth.refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_auth_users_email ON auth.users(email);
CREATE INDEX idx_auth_refresh_tokens_user ON auth.refresh_tokens(user_id);
CREATE INDEX idx_auth_refresh_tokens_expires ON auth.refresh_tokens(expires_at);

-- ============================================
-- Users Schema - User Profiles
-- ============================================

CREATE TABLE IF NOT EXISTS users.profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    avatar_url VARCHAR(500),
    department VARCHAR(100),
    position VARCHAR(100),
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_users_profiles_user ON users.profiles(user_id);
CREATE INDEX idx_users_profiles_department ON users.profiles(department);

-- ============================================
-- Roles Schema - Roles and Permissions
-- ============================================

CREATE TABLE IF NOT EXISTS roles.roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    description VARCHAR(500),
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS roles.permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description VARCHAR(500),
    resource VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS roles.role_permissions (
    role_id UUID NOT NULL REFERENCES roles.roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES roles.permissions(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS roles.user_roles (
    user_id UUID NOT NULL,
    role_id UUID NOT NULL REFERENCES roles.roles(id) ON DELETE CASCADE,
    assigned_by UUID,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (user_id, role_id)
);

CREATE INDEX idx_roles_user_roles_user ON roles.user_roles(user_id);
CREATE INDEX idx_roles_role_permissions_role ON roles.role_permissions(role_id);

-- ============================================
-- Seed Data - Default Roles and Permissions
-- ============================================

INSERT INTO roles.roles (name, description, is_system) VALUES
    ('super_admin', 'Full system access', TRUE),
    ('admin', 'Administrative access', TRUE),
    ('manager', 'Manager level access', TRUE),
    ('user', 'Regular user access', TRUE)
ON CONFLICT (name) DO NOTHING;

INSERT INTO roles.permissions (code, name, description, resource, action) VALUES
    ('users:read', 'Read Users', 'View user profiles', 'users', 'read'),
    ('users:create', 'Create Users', 'Create new users', 'users', 'create'),
    ('users:update', 'Update Users', 'Update user profiles', 'users', 'update'),
    ('users:delete', 'Delete Users', 'Delete user accounts', 'users', 'delete'),
    ('roles:read', 'Read Roles', 'View roles and permissions', 'roles', 'read'),
    ('roles:create', 'Create Roles', 'Create new roles', 'roles', 'create'),
    ('roles:update', 'Update Roles', 'Modify roles', 'roles', 'update'),
    ('roles:delete', 'Delete Roles', 'Delete roles', 'roles', 'delete'),
    ('roles:assign', 'Assign Roles', 'Assign roles to users', 'roles', 'assign'),
    ('audit:read', 'Read Audit Logs', 'View audit trail', 'audit', 'read'),
    ('ai:query', 'AI Queries', 'Query AI agent', 'ai', 'query'),
    ('system:config', 'System Config', 'Modify system configuration', 'system', 'config')
ON CONFLICT (code) DO NOTHING;

-- Assign all permissions to super_admin
INSERT INTO roles.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles.roles r, roles.permissions p
WHERE r.name = 'super_admin'
ON CONFLICT DO NOTHING;

-- Assign specific permissions to admin
INSERT INTO roles.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles.roles r, roles.permissions p
WHERE r.name = 'admin'
  AND p.code IN ('users:read', 'users:create', 'users:update', 'users:delete',
                 'roles:read', 'roles:assign', 'audit:read', 'ai:query')
ON CONFLICT DO NOTHING;

-- Assign limited permissions to manager
INSERT INTO roles.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles.roles r, roles.permissions p
WHERE r.name = 'manager'
  AND p.code IN ('users:read', 'users:update', 'audit:read', 'ai:query')
ON CONFLICT DO NOTHING;

-- Assign basic permissions to user
INSERT INTO roles.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles.roles r, roles.permissions p
WHERE r.name = 'user'
  AND p.code IN ('users:read', 'ai:query')
ON CONFLICT DO NOTHING;