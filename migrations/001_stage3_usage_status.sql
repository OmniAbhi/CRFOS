-- Apply once to databases created before Stage 3.
ALTER TABLE usage_records
    ADD COLUMN usage_status ENUM('SCHEDULED', 'IN_USE', 'COMPLETED', 'CANCELLED', 'NO_SHOW', 'PARTIALLY_USED')
    NOT NULL DEFAULT 'COMPLETED' AFTER actual_occupancy;
