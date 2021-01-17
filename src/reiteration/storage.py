import os
import pickle
import sqlite3
from contextlib import contextmanager
from datetime import datetime


@contextmanager
def cursor(connection):
    c = connection.cursor()
    try:
        yield c
    finally:
        connection.commit()
        c.close()


class MemoryStore:

    def __init__(self):
        self.data = {}

    def store(self, key, obj, **kwargs):
        self.data[key] = obj

    def get(self, key, raise_key_error=False):
        if raise_key_error:
            return self.data[key]
        else:
            return self.data.get(key)

    def exists(self, key):
        return key in self.data

    def delete(self, key):
        self.data.pop(key)


class SqliteStore:

    def _get_now_str(self):
        return datetime.utcnow().isoformat()

    def __init__(self, data_dir, db_file_name=None):
        if not os.path.isdir(data_dir):
            os.mkdir(data_dir)
        path = os.path.expanduser(data_dir)
        db_file_name = db_file_name or 'stash_data.db'
        self.conn = sqlite3.connect(os.path.join(path, db_file_name))
        with cursor(self.conn) as c:
            c.execute('''CREATE TABLE IF NOT EXISTS data
             (key text primary key, tag text, value text, timestamp text)''')

    def store(self, key, obj, tag=None):
        obj_pickle = pickle.dumps(obj)
        with cursor(self.conn) as c:
            data = (str(key), str(tag), obj_pickle, self._get_now_str())
            c.execute('REPLACE INTO data VALUES (?, ?, ?, ?)', data)

    def get(self, key, raise_key_error=False):
        key = str(key)
        with cursor(self.conn) as c:
            data = c.execute('SELECT value from data where key = ?', (key,))
            o = data.fetchone()
            if raise_key_error and not o:
                raise KeyError(f'{key} not in store')
            elif o:
                return pickle.loads(o[0])

    def exists(self, key):
        with cursor(self.conn) as c:
            data = c.execute('SELECT EXISTS(SELECT 1 FROM data WHERE key=?)', (key,))
            v = data.fetchone()[0]
        return v

    def ls(self, tag=None):
        for index, item in enumerate(self._ls(tag=tag)):
            print(f'{index}: {item}')

    def delete(self, key):
        key = str(key)
        with cursor(self.conn) as c:
            c.execute(f'DELETE FROM data WHERE key = ?', (key,))

    def delete_by_index(self, index):
        items = self._ls()
        if index < len(items):
            self.delete(items[index])

    def delete_by_tag(self, tag):
        with cursor(self.conn) as c:
            c.execute(f'DELETE FROM data WHERE tag = ?', (tag,))

    def delete_older(self, ref_time_utc):
        with cursor(self.conn) as c:
            c.execute('DELETE FROM data WHERE timestamp < ?', (ref_time_utc.isoformat(),))

    def _ls(self, tag=None):
        items = []
        with cursor(self.conn) as c:
            sql = 'SELECT key FROM data'
            if tag:
                sql += ' WHERE tag = ?'
            data = c.execute(sql) if not tag else c.execute(sql, (tag,))
            for index, name in enumerate(data):
                items.append(name[0])
        return items

    def close(self):
        self.conn.close()


class NoOpCallable:
    def __init__(self, name):
        self.name = name

    def __call__(self, *args, **kwargs):
        self.__str__()

    def __str__(self):
        return f'{self.name}/Stash not configured, create config in ~/.stashed/config'


class NoOpStash:

    def __getattr__(self, attr):
        return NoOpCallable(attr)
