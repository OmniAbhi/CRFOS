-- CRFOS database foundation. This file never drops existing data.
CREATE DATABASE IF NOT EXISTS crfos
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE crfos;

CREATE TABLE IF NOT EXISTS departments (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    code VARCHAR(20) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_departments_name (name),
    UNIQUE KEY uq_departments_code (code)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS users (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    department_id BIGINT UNSIGNED NULL,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL,
    role ENUM('STUDENT', 'FACULTY', 'DEPARTMENT_ADMIN', 'FINANCE', 'MAINTENANCE', 'ADMIN') NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_users_email (email),
    KEY idx_users_department (department_id),
    CONSTRAINT fk_users_department FOREIGN KEY (department_id)
        REFERENCES departments (id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS resources (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    department_id BIGINT UNSIGNED NULL,
    name VARCHAR(150) NOT NULL,
    resource_type VARCHAR(80) NOT NULL,
    location VARCHAR(150) NULL,
    capacity INT UNSIGNED NULL,
    status ENUM('AVAILABLE', 'UNAVAILABLE', 'MAINTENANCE', 'RETIRED') NOT NULL DEFAULT 'AVAILABLE',
    description TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_resources_department (department_id),
    KEY idx_resources_type_status (resource_type, status),
    CONSTRAINT fk_resources_department FOREIGN KEY (department_id)
        REFERENCES departments (id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS bookings (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    resource_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    department_id BIGINT UNSIGNED NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    purpose VARCHAR(255) NOT NULL,
    status ENUM('PENDING', 'APPROVED', 'CANCELLED', 'COMPLETED', 'NO_SHOW') NOT NULL DEFAULT 'PENDING',
    expected_occupancy INT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_bookings_resource_time (resource_id, start_time, end_time),
    KEY idx_bookings_user_time (user_id, start_time),
    KEY idx_bookings_status (status),
    CONSTRAINT chk_bookings_time_range CHECK (end_time > start_time),
    CONSTRAINT fk_bookings_resource FOREIGN KEY (resource_id)
        REFERENCES resources (id) ON DELETE RESTRICT,
    CONSTRAINT fk_bookings_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_bookings_department FOREIGN KEY (department_id)
        REFERENCES departments (id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS usage_records (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    booking_id BIGINT UNSIGNED NULL,
    resource_id BIGINT UNSIGNED NOT NULL,
    planned_start_time DATETIME NULL,
    planned_end_time DATETIME NULL,
    actual_start_time DATETIME NULL,
    actual_end_time DATETIME NULL,
    planned_duration_minutes INT UNSIGNED NULL,
    actual_duration_minutes INT UNSIGNED NULL,
    actual_occupancy INT UNSIGNED NULL,
    capacity_at_usage INT UNSIGNED NULL,
    idle_time_minutes INT UNSIGNED NULL,
    is_phantom_booking BOOLEAN NOT NULL DEFAULT FALSE,
    usage_status ENUM('SCHEDULED', 'IN_USE', 'COMPLETED', 'CANCELLED', 'NO_SHOW', 'PARTIALLY_USED') NOT NULL DEFAULT 'COMPLETED',
    source VARCHAR(80) NULL,
    notes TEXT NULL,
    recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_usage_records_booking (booking_id),
    KEY idx_usage_records_resource_time (resource_id, actual_start_time),
    KEY idx_usage_records_booking (booking_id),
    CONSTRAINT chk_usage_time_range CHECK (
        actual_end_time IS NULL OR actual_start_time IS NULL OR actual_end_time >= actual_start_time
    ),
    CONSTRAINT chk_usage_planned_time_range CHECK (
        planned_end_time IS NULL OR planned_start_time IS NULL OR planned_end_time >= planned_start_time
    ),
    CONSTRAINT fk_usage_records_booking FOREIGN KEY (booking_id)
        REFERENCES bookings (id) ON DELETE SET NULL,
    CONSTRAINT fk_usage_records_resource FOREIGN KEY (resource_id)
        REFERENCES resources (id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS suppliers (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    contact_name VARCHAR(120) NULL,
    email VARCHAR(255) NULL,
    phone VARCHAR(40) NULL,
    address TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_suppliers_name (name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS purchases (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    resource_id BIGINT UNSIGNED NULL,
    supplier_id BIGINT UNSIGNED NULL,
    department_id BIGINT UNSIGNED NULL,
    item_name VARCHAR(150) NOT NULL,
    quantity INT UNSIGNED NOT NULL,
    unit_cost DECIMAL(12, 2) NOT NULL,
    total_cost DECIMAL(14, 2) NOT NULL,
    purchase_date DATE NOT NULL,
    purchase_order_number VARCHAR(80) NULL,
    procurement_notes TEXT NULL,
    purpose VARCHAR(255) NULL,
    status ENUM('PLANNED', 'ORDERED', 'RECEIVED', 'CANCELLED') NOT NULL DEFAULT 'PLANNED',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_purchases_department_date (department_id, purchase_date),
    KEY idx_purchases_supplier (supplier_id),
    KEY idx_purchases_resource (resource_id),
    KEY idx_purchases_purchase_date (purchase_date),
    CONSTRAINT chk_purchases_quantity CHECK (quantity > 0),
    CONSTRAINT chk_purchases_cost CHECK (unit_cost >= 0 AND total_cost >= 0),
    CONSTRAINT fk_purchases_resource FOREIGN KEY (resource_id)
        REFERENCES resources (id) ON DELETE SET NULL,
    CONSTRAINT fk_purchases_supplier FOREIGN KEY (supplier_id)
        REFERENCES suppliers (id) ON DELETE SET NULL,
    CONSTRAINT fk_purchases_department FOREIGN KEY (department_id)
        REFERENCES departments (id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sharing_requests (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    requesting_department_id BIGINT UNSIGNED NOT NULL,
    requesting_user_id BIGINT UNSIGNED NULL,
    source_department_id BIGINT UNSIGNED NULL,
    requested_resource_id BIGINT UNSIGNED NULL,
    requested_resource_type VARCHAR(80) NULL,
    matched_resource_id BIGINT UNSIGNED NULL,
    requested_quantity INT UNSIGNED NOT NULL DEFAULT 1,
    reason TEXT NOT NULL,
    request_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status ENUM('PENDING', 'APPROVED', 'REJECTED', 'COMPLETED', 'CANCELLED') NOT NULL DEFAULT 'PENDING',
    approved_by_user_id BIGINT UNSIGNED NULL,
    approved_at DATETIME NULL,
    KEY idx_sharing_requests_status_date (status, request_date),
    KEY idx_sharing_requests_requesting_department (requesting_department_id),
    KEY idx_sharing_requests_requesting_user (requesting_user_id),
    CONSTRAINT fk_sharing_requests_requesting_department FOREIGN KEY (requesting_department_id)
        REFERENCES departments (id) ON DELETE RESTRICT,
    CONSTRAINT fk_sharing_requests_requesting_user FOREIGN KEY (requesting_user_id)
        REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_sharing_requests_source_department FOREIGN KEY (source_department_id)
        REFERENCES departments (id) ON DELETE SET NULL,
    CONSTRAINT fk_sharing_requests_requested_resource FOREIGN KEY (requested_resource_id)
        REFERENCES resources (id) ON DELETE SET NULL,
    CONSTRAINT fk_sharing_requests_matched_resource FOREIGN KEY (matched_resource_id)
        REFERENCES resources (id) ON DELETE SET NULL,
    CONSTRAINT fk_sharing_requests_approved_by FOREIGN KEY (approved_by_user_id)
        REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS predictions (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    resource_id BIGINT UNSIGNED NULL,
    resource_type VARCHAR(80) NULL,
    prediction_date DATE NOT NULL,
    target_start_date DATE NOT NULL,
    target_end_date DATE NOT NULL,
    predicted_demand DECIMAL(12, 2) NOT NULL,
    actual_demand DECIMAL(12, 2) NULL,
    prediction_error DECIMAL(12, 2) NULL,
    model_version VARCHAR(100) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_predictions_target_period (target_start_date, target_end_date),
    KEY idx_predictions_resource (resource_id),
    CONSTRAINT chk_predictions_target CHECK (target_end_date >= target_start_date),
    CONSTRAINT fk_predictions_resource FOREIGN KEY (resource_id)
        REFERENCES resources (id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS maintenance_records (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    resource_id BIGINT UNSIGNED NOT NULL,
    technician_user_id BIGINT UNSIGNED NULL,
    maintenance_type VARCHAR(80) NOT NULL,
    description TEXT NOT NULL,
    status ENUM('SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED') NOT NULL DEFAULT 'SCHEDULED',
    reported_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    scheduled_date DATETIME NULL,
    completed_date DATETIME NULL,
    downtime_minutes INT UNSIGNED NULL,
    cost DECIMAL(12, 2) NULL,
    notes TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_maintenance_resource_status (resource_id, status),
    KEY idx_maintenance_scheduled_date (scheduled_date),
    KEY idx_maintenance_reported_date (reported_date),
    CONSTRAINT chk_maintenance_cost CHECK (cost IS NULL OR cost >= 0),
    CONSTRAINT fk_maintenance_resource FOREIGN KEY (resource_id)
        REFERENCES resources (id) ON DELETE RESTRICT,
    CONSTRAINT fk_maintenance_technician FOREIGN KEY (technician_user_id)
        REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sensor_readings (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    resource_id BIGINT UNSIGNED NOT NULL,
    recorded_at DATETIME NOT NULL,
    sensor_type VARCHAR(80) NOT NULL,
    reading_value DECIMAL(14, 4) NOT NULL,
    unit VARCHAR(30) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_sensor_readings_resource_time (resource_id, recorded_at),
    CONSTRAINT fk_sensor_readings_resource FOREIGN KEY (resource_id)
        REFERENCES resources (id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS notifications (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    notification_type VARCHAR(80) NOT NULL,
    title VARCHAR(150) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at DATETIME NULL,
    KEY idx_notifications_user_read (user_id, is_read, created_at),
    CONSTRAINT fk_notifications_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB;
