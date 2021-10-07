from llpp import start_http_server, start_udp_server, PrintLogHandler, WsLogHandler, SqliteLogHandler
from sys import argv

store_path = './testdb' if len(argv) < 2 else argv[1]
handlers = [
    # PrintLogHandler(), 
    WsLogHandler('localhost', 8085, store_path), 
    SqliteLogHandler(store_path)
]

start_http_server('localhost', 8084)
start_udp_server('localhost', 12345, handlers)
