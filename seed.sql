-- Small synthetic demonstration dataset for CRFOS. Run after schema.sql.

INSERT INTO departments (name, code) VALUES
    ('Computer Science', 'CSE'),
    ('Mechanical Engineering', 'MECH'),
    ('Administration', 'ADMIN');

INSERT INTO users (department_id, full_name, email, role) VALUES
    ((SELECT id FROM departments WHERE code = 'CSE'), 'Asha Nair', 'asha.nair@example.edu', 'FACULTY'),
    ((SELECT id FROM departments WHERE code = 'MECH'), 'Rahul Menon', 'rahul.menon@example.edu', 'DEPARTMENT_ADMIN'),
    ((SELECT id FROM departments WHERE code = 'ADMIN'), 'Maya Thomas', 'maya.thomas@example.edu', 'ADMIN');

INSERT INTO resources (department_id, name, resource_type, location, capacity) VALUES
    ((SELECT id FROM departments WHERE code = 'CSE'), 'Computer Lab 101', 'Laboratory', 'Block A, Room 101', 40),
    ((SELECT id FROM departments WHERE code = 'MECH'), 'Engineering Lab 02', 'Laboratory', 'Block C, Room 02', 30),
    ((SELECT id FROM departments WHERE code = 'ADMIN'), 'Epson Projector 14', 'Projector', 'Central Stores', 1);

INSERT INTO bookings (resource_id, user_id, department_id, start_time, end_time, purpose, status, expected_occupancy) VALUES
    ((SELECT id FROM resources WHERE name = 'Computer Lab 101'), (SELECT id FROM users WHERE email = 'asha.nair@example.edu'), (SELECT id FROM departments WHERE code = 'CSE'), '2026-09-15 09:00:00', '2026-09-15 12:00:00', 'Programming laboratory', 'COMPLETED', 35),
    ((SELECT id FROM resources WHERE name = 'Engineering Lab 02'), (SELECT id FROM users WHERE email = 'rahul.menon@example.edu'), (SELECT id FROM departments WHERE code = 'MECH'), '2026-09-16 10:00:00', '2026-09-16 13:00:00', 'Workshop session', 'NO_SHOW', 25);

-- First booking is underutilized; the NO_SHOW booking has no usage record (phantom booking).
INSERT INTO usage_records (booking_id, resource_id, actual_start_time, actual_end_time, actual_occupancy, source) VALUES
    ((SELECT b.id FROM bookings b JOIN resources r ON r.id = b.resource_id WHERE r.name = 'Computer Lab 101'), (SELECT id FROM resources WHERE name = 'Computer Lab 101'), '2026-09-15 09:30:00', '2026-09-15 10:30:00', 8, 'MANUAL');

INSERT INTO suppliers (name, contact_name, email, phone) VALUES
    ('Campus Tech Supplies', 'Nikhil Varma', 'sales@campustech.example', '555-0101');

INSERT INTO purchases (supplier_id, department_id, item_name, quantity, unit_cost, total_cost, purchase_date, purpose, status) VALUES
    ((SELECT id FROM suppliers WHERE name = 'Campus Tech Supplies'), (SELECT id FROM departments WHERE code = 'CSE'), 'Wireless Presenter', 3, 1200.00, 3600.00, '2026-09-01', 'Teaching support', 'RECEIVED');

INSERT INTO sharing_requests (requesting_department_id, source_department_id, requested_resource_type, matched_resource_id, reason, status, approved_by_user_id, approved_at) VALUES
    ((SELECT id FROM departments WHERE code = 'CSE'), (SELECT id FROM departments WHERE code = 'ADMIN'), 'Projector', (SELECT id FROM resources WHERE name = 'Epson Projector 14'), 'Guest lecture support', 'APPROVED', (SELECT id FROM users WHERE email = 'maya.thomas@example.edu'), '2026-09-10 14:00:00');

INSERT INTO maintenance_records (resource_id, technician_user_id, maintenance_type, description, status, scheduled_date, completed_date, cost) VALUES
    ((SELECT id FROM resources WHERE name = 'Epson Projector 14'), (SELECT id FROM users WHERE email = 'maya.thomas@example.edu'), 'Inspection', 'Lamp-hour inspection', 'COMPLETED', '2026-09-05 10:00:00', '2026-09-05 11:00:00', 0.00);
