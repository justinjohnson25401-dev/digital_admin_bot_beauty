
from .database import Database
from .user_queries import UserQueries
from .booking_queries import BookingQueries
from .staff_queries import StaffQueries
from .stats_queries import StatsQueries

class DBManager(Database, UserQueries, BookingQueries, StaffQueries, StatsQueries):
    def __init__(self, business_slug: str):
        Database.__init__(self, business_slug)
        # Инициализация базовых классов с передачей self.connection
        UserQueries.__init__(self, self.connection)
        BookingQueries.__init__(self, self.connection)
        StaffQueries.__init__(self, self.connection)
        StatsQueries.__init__(self, self.connection)

    def init_db(self):
        super().init_db() # Вызов init_db из класса Database
        # После инициализации БД, пересоздаем экземпляры классов запросов с активным соединением
        self.connection = super().connection
        UserQueries.__init__(self, self.connection)
        BookingQueries.__init__(self, self.connection)
        StaffQueries.__init__(self, self.connection)
        StatsQueries.__init__(self, self.connection)
