CREATE DATABASE IF NOT EXISTS smart_library;
USE smart_library;

CREATE TABLE IF NOT EXISTS users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    google_id VARCHAR(191) NULL UNIQUE,
    role ENUM('student', 'librarian', 'admin') NOT NULL,
    account_status ENUM('active', 'inactive') NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id INT PRIMARY KEY,
    membership_code VARCHAR(40) NOT NULL UNIQUE,
    profession_title VARCHAR(80) NOT NULL,
    department VARCHAR(120) DEFAULT 'General',
    bio TEXT NULL,
    profile_image_url VARCHAR(255) NULL,
    joined_on DATE NOT NULL,
    avatar_color VARCHAR(20) DEFAULT '#f97316',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS books (
    id INT PRIMARY KEY AUTO_INCREMENT,
    book_code VARCHAR(40) NOT NULL UNIQUE,
    google_book_id VARCHAR(100) NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    author_name VARCHAR(255) NOT NULL,
    isbn VARCHAR(32) NULL,
    thumbnail_url TEXT NULL,
    category VARCHAR(150) NOT NULL,
    description TEXT NULL,
    cover_url TEXT NULL,
    published_date VARCHAR(50) NULL,
    total_copies INT NOT NULL DEFAULT 5,
    available_copies INT NOT NULL DEFAULT 5,
    status ENUM('Available', 'Issued') NOT NULL DEFAULT 'Available',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE users ADD COLUMN google_id VARCHAR(191) NULL UNIQUE AFTER password_hash;

CREATE TABLE IF NOT EXISTS borrow_records (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    book_id INT NOT NULL,
    issued_by INT NULL,
    issued_at DATETIME NOT NULL,
    due_at DATETIME NOT NULL,
    returned_at DATETIME NULL,
    fine_amount DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    status ENUM('issued', 'returned', 'overdue') NOT NULL DEFAULT 'issued',
    notes VARCHAR(255) NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (issued_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS students (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NULL UNIQUE,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    status ENUM('Issued', 'Returned', 'Overdue') NOT NULL DEFAULT 'Issued',
    book_id INT NOT NULL,
    student_id INT NOT NULL,
    issue_date DATE NOT NULL,
    return_date DATE NULL,
    due_date DATE NOT NULL,
    fine_amount DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    fine_per_day DECIMAL(10, 2) NOT NULL DEFAULT 10.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS fine_payments (
    id INT PRIMARY KEY AUTO_INCREMENT,
    transaction_id INT NOT NULL,
    paid_by_user_id INT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    payment_reference VARCHAR(64) NOT NULL UNIQUE,
    payment_mode VARCHAR(30) NOT NULL DEFAULT 'simulation',
    payment_status ENUM('paid') NOT NULL DEFAULT 'paid',
    paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
    FOREIGN KEY (paid_by_user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_status ON users(account_status);
CREATE INDEX idx_borrow_user ON borrow_records(user_id);
CREATE INDEX idx_borrow_status ON borrow_records(status);
CREATE INDEX idx_books_status ON books(status);
CREATE INDEX idx_students_user ON students(user_id);
CREATE INDEX idx_transactions_book_status ON transactions(book_id, status);
CREATE INDEX idx_transactions_student_status ON transactions(student_id, status);
CREATE INDEX idx_fine_payments_transaction ON fine_payments(transaction_id);
