from abc import ABC
import struct
import socket
from typing import Iterable, List, Tuple
from sqlite3 import connect as sqlite3_connect
from datetime import datetime, timedelta
from websockets import serve as ws_serve
from asyncio import new_event_loop, run_coroutine_threadsafe
from threading import Thread
import json


class LogHandler(ABC):
    def log_status(self, station, status):
        pass
    def log_arrival(self, station):
        pass
    def log_departure(self, station, service_nanos):
        pass


class PrintLogHandler(LogHandler):
    def __init__(self) -> None:
        self.count = 0
    def log_status(self, station, status):
        self.count += 1
        print(self.count, 'Status of', station, 'is', status)
    def log_arrival(self, station):
        print('Arrival at', station)
    def log_departure(self, station, service_nanos):
        print('Departure from', station, 'after', service_nanos, 'ns')


class SqliteLogHandler(LogHandler):
    """
    Some technical notes:
    - We can measure performance in nanoseconds and store durations as 64bit integers.
    - A 64bit integer can safely accumulate more than 100 years of total duration in nanoseconds.
    - A 64bit integer can safely represent the square of a duration of 6 years in nanoseconds.
    """
    def __init__(self, path):
        self.db = sqlite3_connect(path)
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS llpp_status (
                station TEXT NOT NULL PRIMARY KEY,
                status TEXT NOT NULL,
                ts DATETIME NOT NULL
            );
            CREATE TABLE IF NOT EXISTS llpp_arrivals (
                station TEXT NOT NULL,
                start DATETIME NOT NULL,
                end DATETIME NOT NULL,
                count INT NOT NULL,
                PRIMARY KEY (station, start, end)
            );
            CREATE TABLE IF NOT EXISTS llpp_departures (
                station TEXT NOT NULL,
                start DATETIME NOT NULL,
                end DATETIME NOT NULL,
                count INT NOT NULL,
                open INT NOT NULL,
                close INT NOT NULL,
                low INT NOT NULL,
                high INT NOT NULL,
                total INT NOT NULL,
                squares INT NOT NULL,
                mean INT GENERATED ALWAYS AS (total / count) VIRTUAL,
                var INT GENERATED ALWAYS AS (squares / count - mean * mean) VIRTUAL, 
                PRIMARY KEY (station, start, end)
            );
        ''')
    def _get_timestamp(self) -> Tuple[str, str, str]:
        now = datetime.utcnow()
        start = now.replace(minute=(now.minute//10)*10, second=0, microsecond=0)
        end = start + timedelta(minutes=10)
        return start.isoformat(), now.isoformat(), end.isoformat()
    def log_status(self, station, status):
        tf = self._get_timestamp()
        self.db.execute('INSERT OR REPLACE INTO llpp_status (station, status, ts) VALUES (?, ?, ?)', (station, status, tf[1]))
        # self.db.commit()  # NOTE: You may prefere to skip commit on log_status
    def log_arrival(self, station):
        tf = self._get_timestamp()
        self.db.execute('INSERT OR IGNORE INTO llpp_arrivals (station, start, end, count) VALUES (?, ?, ?, 0)', (station, tf[0], tf[2]))
        self.db.execute('UPDATE llpp_arrivals SET count = count + 1 WHERE station = ? AND start = ? AND end = ?', (station, tf[0], tf[2]))
        # self.db.commit()  # NOTE: You may prefere to skip commit on log_arrival
    def log_departure(self, station, service_nanos):
        x = int(service_nanos)
        tf = self._get_timestamp()
        self.db.execute('INSERT OR IGNORE INTO llpp_departures (station, start, end, count, open, close, low, high, total, squares) VALUES (?, ?, ?, 0, ?, ?, ?, ?, 0, 0)', (station, tf[0], tf[2], x, x, x, x))
        self.db.execute('''
            UPDATE llpp_departures 
            SET count = count + 1,
                close = ?,
                low = MIN(low, ?),
                high = MAX(high, ?),
                total = total + ?,
                squares = squares + ?    
            WHERE station = ? AND start = ? AND end = ? ''', 
            (x, x, x, x, x**2, station, tf[0], tf[2]))
        self.db.commit()


class ReadableSqliteLogHandler(SqliteLogHandler):
    def list_stations(self) -> List[str]:
        c = self.db.execute('''
            SELECT DISTINCT station FROM llpp_status
            UNION SELECT DISTINCT station FROM llpp_arrivals
            UNION SELECT DISTINCT station FROM llpp_departures
        ''')
        return [row[0] for row in c]
    def get_status(self, station) -> Tuple[str, str]:
        c = self.db.execute('SELECT status, ts FROM llpp_status WHERE station = ?', (station,))
        for row in c:
            return row[0], row[1]
    def get_past_arrivals(self, station) -> Iterable[tuple]:
        c = self.db.execute('SELECT start, end, count FROM llpp_arrivals WHERE station = ?', (station,))
        yield from c
    def get_past_departures(self, station) -> Iterable[tuple]:
        c = self.db.execute('SELECT start, end, count, open, low, high, close, mean, var FROM llpp_departures WHERE station = ?', (station,))
        yield from c


class WsLogHandler(LogHandler):
    def __init__(self, addr: str, port: int, store_path: str):
        self.sockets = dict()

        async def _handler(ws, path: str):
            self.sockets[ws] = None
            store = ReadableSqliteLogHandler(store_path)
            async for query in ws:
                query = json.loads(query)
                if query == 'list_stations':
                    await ws.send(json.dumps({
                        'stations': store.list_stations()
                    }))
                elif isinstance(query, dict) and 'station' in query:
                    station = query['station']
                    await ws.send(json.dumps({
                        'past': {
                            'station': station,
                            'status': store.get_status(station),
                            'arrivals': list(store.get_past_arrivals(station)),
                            'departures': list(store.get_past_departures(station)),
                        }
                    }))
                    self.sockets[ws] = query
            del self.sockets[ws]
        
        def _job():
            self.loop = new_event_loop()
            self.loop.run_until_complete(ws_serve(_handler, addr, port, loop=self.loop))
            print('WS server ready to accept connections on', addr, port)
            self.loop.run_forever()

        Thread(target=_job, name="WSS", daemon=True).start()
    
    async def _handle_log(self, type, station, *args):
        for sock, query in self.sockets.items():
            if query and 'station' in query and query['station'] == station:
                await sock.send(json.dumps({'log': [type, station, *args]}))
        
    def log_status(self, station, status):
        run_coroutine_threadsafe(self._handle_log('status', station, status), self.loop)
    def log_arrival(self, station):
        run_coroutine_threadsafe(self._handle_log('arrival', station), self.loop)
    def log_departure(self, station, service_nanos):
        run_coroutine_threadsafe(self._handle_log('departure', station, service_nanos), self.loop)


def start_http_server(addr: str, port: int):
    # TODO: start HTTP server for single file
    pass


def start_udp_server(addr: str, port: int, handlers: List[LogHandler]):
    frame_fmt = '!8sBB'
    frame_nanos_fmt = '!Q'
    frame_h_size = struct.calcsize(frame_fmt)
    frame_nanos_size = struct.calcsize(frame_nanos_fmt)

    # Create UDP socket and bind it to receive packets
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
        sock.bind((addr, port))
        print('UDP socket ready to receive on', addr, port)
        while True:
            # Receive one UDP datagram
            data = sock.recv(1024)
            # Decode it into <header, station, content>
            header, len1, len2 = struct.unpack(frame_fmt, data[:frame_h_size])
            station = data[frame_h_size:frame_h_size+len1].decode('utf8')
            content = data[frame_h_size+len1:frame_h_size+len1+len2]
            # Dispatch it to the log handlers
            if header == b'llppstts':
                status = content.decode('utf8')
                for h in handlers:
                    h.log_status(station, status)
            if header == b'llpprrvl' and len2 == 0:
                for h in handlers:
                    h.log_arrival(station)
            if header == b'llppdprt' and len2 == frame_nanos_size:
                service_nanos, = struct.unpack(frame_nanos_fmt, content)
                for h in handlers:
                    h.log_departure(station, service_nanos)
