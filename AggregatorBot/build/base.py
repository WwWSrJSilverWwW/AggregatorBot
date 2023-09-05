import sqlite3


class DataBase:
    def __init__(self, file_name):
        self.file_name = file_name

    def open(self):
        self.con = sqlite3.connect(self.file_name)
        self.cur = self.con.cursor()

    def insert(self, table, **kwargs):
        self.open()
        keys = "('" + "','".join(kwargs.keys()) + "')"
        values = "('" + "','".join(kwargs.values()) + "')"
        self.cur.execute(f"INSERT INTO {table} {keys} VALUES {values}")
        self.con.commit()
        self.close()

    def select(self, table, type="AND", **kwargs):
        self.open()
        if len(kwargs) == 0:
            wh = ""
        else:
            wh = " WHERE " + f" {type} ".join([f"{x[0]} = '{x[1]}'" for x in kwargs.items()])
        self.close()
        return self.cur.execute(f"SELECT * FROM {table}{wh}")

    def update(self, table, type="AND", **kwargs):
        self.open()
        st = f" SET {list(kwargs.items())[0][0]} = '{list(kwargs.items())[0][1]}'"
        wh = " WHERE " + f" {type} ".join([f"{x[0]} = '{x[1]}'" for x in list(kwargs.items())[1:]])
        self.cur.execute(f"UPDATE {table}{st}{wh}")
        self.con.commit()
        self.close()

    def delete(self, table, type="AND", **kwargs):
        self.open()
        wh = " WHERE " + f" {type} ".join([f"{x[0]} = '{x[1]}'" for x in kwargs.items()])
        self.cur.execute(f"DELETE FROM {table}{wh}")
        self.con.commit()
        self.close()

    def exec(self, quest):
        self.open()
        self.cur.execute(quest)
        self.con.commit()
        self.close()

    def close(self):
        self.con.close()
