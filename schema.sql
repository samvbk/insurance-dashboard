-- Drop tables if they exist to ensure a clean start
DROP TABLE IF EXISTS Documents;
DROP TABLE IF EXISTS Policies;
DROP TABLE IF EXISTS Agencies; -- Dropping new table
DROP TABLE IF EXISTS Clients;

-- Create the Agencies table (NEW)
CREATE TABLE Agencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- Create the Clients table with new fields for address, dob, and nominee
CREATE TABLE Clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    address TEXT, -- NEW
    dob TEXT, -- NEW
    nominee_name TEXT, -- NEW
    nominee_dob TEXT, -- NEW
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create the Policies table (no changes needed here, but kept for completeness)
CREATE TABLE Policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    policy_number TEXT,
    vehicle_number TEXT,
    vehicle_type TEXT,
    agency TEXT,
    policy_type TEXT,
    insurance_company TEXT,
    premium REAL,
    policy_start_date TEXT,
    policy_end_date TEXT,
    account_details TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES Clients (id) ON DELETE CASCADE
);

-- Create the Documents table
CREATE TABLE Documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES Clients (id) ON DELETE CASCADE
);