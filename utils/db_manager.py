import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path="booking_bot.db"):
        try:
            self.conn = sqlite3.connect(db_path)
            self.conn.row_factory = self.dict_factory
            self.cursor = self.conn.cursor()
            self._init_db()
            logger.info(f"Successfully connected to database at {db_path}")
        except sqlite3.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise

    @staticmethod
    def dict_factory(cursor, row):
        """Makes the query results to be dictionaries instead of tuples."""
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def _init_db(self):
        """Initializes the database schema by creating necessary tables."""
        try:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    client_name TEXT NOT NULL,
                    phone TEXT,
                    service_id TEXT NOT NULL,
                    service_name TEXT NOT NULL,
                    master_id TEXT,
                    master_name TEXT,
                    booking_datetime TEXT NOT NULL UNIQUE,
                    comment TEXT,
                    price REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS client_details (
                    user_id INTEGER PRIMARY KEY,
                    client_name TEXT NOT NULL,
                    phone TEXT NOT NULL
                )
            ''')
            self.conn.commit()
            logger.info("Database tables initialized or already exist.")
        except sqlite3.Error as e:
            logger.error(f"Error initializing database schema: {e}")
            self.conn.rollback() # Rollback changes on error
            raise

    def add_booking(self, user_id, client_name, phone, service_id, service_name, master_id, master_name, booking_datetime, comment, price):
        """Adds a new booking to the database."""
        try:
            sql = '''
                INSERT INTO bookings (user_id, client_name, phone, service_id, service_name, master_id, master_name, booking_datetime, comment, price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
            self.cursor.execute(sql, (user_id, client_name, phone, service_id, service_name, master_id, master_name, booking_datetime, comment, price))
            self.conn.commit()
            booking_id = self.cursor.lastrowid
            logger.info(f"Added new booking with ID {booking_id} for user {user_id}")
            return booking_id
        except sqlite3.IntegrityError as e:
            logger.warning(f"Failed to add booking due to integrity error (likely duplicate datetime): {e}")
            self.conn.rollback()
            return None
        except sqlite3.Error as e:
            logger.error(f"Failed to add booking for user {user_id}: {e}")
            self.conn.rollback()
            return None

    def get_user_bookings(self, user_id):
        """Retrieves all bookings for a given user ID."""
        try:
            self.cursor.execute("SELECT * FROM bookings WHERE user_id = ?", (user_id,))
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Failed to get bookings for user {user_id}: {e}")
            return []

    def cancel_booking(self, booking_id):
        """Cancels (deletes) a booking by its ID."""
        try:
            self.cursor.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
            self.conn.commit()
            if self.cursor.rowcount > 0:
                logger.info(f"Canceled booking with ID {booking_id}")
                return True
            else:
                logger.warning(f"Attempted to cancel non-existent booking with ID {booking_id}")
                return False
        except sqlite3.Error as e:
            logger.error(f"Failed to cancel booking {booking_id}: {e}")
            self.conn.rollback()
            return False

    def get_booking_by_id(self, booking_id):
        """Retrieves a single booking by its ID."""
        try:
            self.cursor.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
            return self.cursor.fetchone()
        except sqlite3.Error as e:
            logger.error(f"Failed to get booking by ID {booking_id}: {e}")
            return None

    def save_last_client_details(self, user_id, client_name, phone):
        """Saves or updates the last used contact details for a user."""
        try:
            sql = '''
                INSERT INTO client_details (user_id, client_name, phone)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    client_name = excluded.client_name,
                    phone = excluded.phone
            '''
            self.cursor.execute(sql, (user_id, client_name, phone))
            self.conn.commit()
            logger.info(f"Saved last details for user {user_id}")
        except sqlite3.Error as e:
            logger.error(f"Failed to save last details for user {user_id}: {e}")
            self.conn.rollback()

    def get_last_client_details(self, user_id):
        """Retrieves the last saved contact details for a user."""
        try:
            self.cursor.execute("SELECT client_name, phone FROM client_details WHERE user_id = ?", (user_id,))
            return self.cursor.fetchone()
        except sqlite3.Error as e:
            logger.error(f"Failed to get last details for user {user_id}: {e}")
            return None

    def get_busy_slots(self, date_str, master_id=None):
        """
        Returns a list of busy time slots (HH:MM format) for a given date string (YYYY-MM-DD).
        If master_id is provided, it filters by that master.
        """
        try:
            if master_id:
                sql = "SELECT strftime('%H:%M', booking_datetime) FROM bookings WHERE date(booking_datetime) = ? AND master_id = ?"
                self.cursor.execute(sql, (date_str, master_id))
            else:
                sql = "SELECT strftime('%H:%M', booking_datetime) FROM bookings WHERE date(booking_datetime) = ?"
                self.cursor.execute(sql, (date_str,))
            
            return [row["strftime('%H:%M', booking_datetime)"] for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Failed to get busy slots for date {date_str} and master {master_id}: {e}")
            return []

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed.")
