import asyncio
import logging
import struct
import pickle
import time

from PyQt5.QtNetwork import QTcpServer, QTcpSocket, QHostAddress
from PyQt5.QtCore import QThread, pyqtSignal

from .utils import show_critical_dialog
from .config import CONFIG


class LogServer(QTcpServer):
    def __init__(self, main_window, on_connection, log, stop_signal):
        super().__init__()
        self.log = log.getChild('TCP')

        self.log.info('Initializing')

        self.main_window = main_window
        self.on_connection = on_connection
        self.stop_signal = stop_signal

        self.host, self.port = CONFIG.listen_address
        self.host = QHostAddress(self.host)
        self.benchmark = CONFIG['benchmark']

        self.threads = {}  # socketDescriptor -> LogConnection
        self.connections = 0

    def start(self):
        self.log.info('Starting the server')
        if self.benchmark:
            self.log.debug('Starting a benchmark connection')
            tab_closed = asyncio.Event()
            new_conn = BenchmarkConnection(self, None, "benchmark",
                                           self.stop_signal, tab_closed, self.log)
            self.on_connection(new_conn, "benchmark", tab_closed)
            self.threads[None] = new_conn
            new_conn.start()

        result = self.listen(self.host, self.port)
        if not result:
            err_string = self.errorString()
            show_critical_dialog(self.main_window, 'Error while starting the server', err_string)
        else:
            self.main_window.set_status(f'Server is listening on {self.host.toString()}:{self.port}...')

    def incomingConnection(self, socketDescriptor):
        self.connections += 1
        name = f'Logger {self.connections}'
        self.log.info(f'New connection: "{name}"')
        tab_closed = asyncio.Event()
        new_conn = LogConnection(self, socketDescriptor, name,
                                 self.stop_signal, tab_closed, self.log)
        self.on_connection(new_conn, name, tab_closed)
        new_conn.finished.connect(new_conn.deleteLater)
        new_conn.connection_finished.connect(self.cleanup_connection)
        new_conn.start()
        self.threads[int(socketDescriptor)] = new_conn

    def close_server(self):
        self.log.debug('Closing the server')
        self.close()
        self.stop_all_connections()

    def stop_all_connections(self):
        self.log.debug('Waiting for connection threads to stop')
        for _, thread in self.threads.items():
            thread.exit()
        for _, thread in self.threads.items():
            if not thread.wait(1000):
                self.log.error(f'Thread "{thread}" didn\'t stop in time, attempring termination')
                thread.terminate()
                self.log.error(f'Thread "{thread}" terminated')
        self.log.debug('All connections stopped')

    def cleanup_connection(self, socketDescriptor):
        try:
            del self.threads[socketDescriptor]
        except Exception as e:
            self.log.error(f'Bad socketDescriptor: {socketDescriptor}', exc_info=True)
            # import pdb; pdb.set_trace()


class LogConnection(QThread):

    new_record = pyqtSignal(logging.LogRecord)
    connection_finished = pyqtSignal(int)

    def __init__(self, parent, socketDescriptor, name, stop_signal, tab_closed, log):
        super().__init__(parent)
        self.log = log.getChild(name)
        # self.parent_object = parent
        self.socketDescriptor = socketDescriptor
        self.name = name
        self.stop_signal = stop_signal
        self.tab_closed = tab_closed

    def run(self):
        self.log.debug(f'Connection "{self.name}" is starting')

        def wait_and_read(n_bytes, wait_ms):
            "Convinience function that simplifies checking for stop events, etc."
            if sock.bytesAvailable() == 0:
                new_data = sock.waitForReadyRead(wait_ms)
                if not new_data:
                    return None
            return sock.read(n_bytes)

        sock = QTcpSocket(None)
        # import pdb; pdb.set_trace()
        sock.setSocketDescriptor(self.socketDescriptor)
        sock.waitForConnected()

        while True:
            if sock.state() != sock.ConnectedState or self.need_to_stop():
                self.log.debug(f'Connection "{self.name}" is stopping')
                break
            read_len = wait_and_read(4, 100)
            if not read_len:
                continue
            read_len = struct.unpack(">L", read_len)[0]

            if sock.bytesAvailable() == 0:
                sock.waitForReadyRead()
            data = sock.read(read_len)
            if not data:
                continue

            data = pickle.loads(data)
            record = logging.makeLogRecord(data)
            self.new_record.emit(record)
        sock.disconnectFromHost()
        sock.close()
        self.connection_finished.emit(int(self.socketDescriptor))
        self.log.debug(f'Connection "{self.name}" has stopped')

    def need_to_stop(self):
        return any([self.stop_signal.is_set(), self.tab_closed.is_set()])


class BenchmarkConnection(LogConnection):

    def run(self):
        test_levels = [(10, 'DEBUG'), (20, 'INFO'), (30, 'WARNING'),
                       (40, 'ERROR'), (50, 'CRITICAL'), (21, 'REQ')]
        d = {'args': None,  # dummy log item
             'created': 0,
             'exc_info': None,
             'exc_text': 'exception test',
             'filename': 'test.py',
             'funcName': 'test_func',
             'levelname': 'DEBUG',
             'levelno': 10,
             'lineno': 119,
             'module': 'test',
             'msecs': 332.2334289550781,
             'msg': "hey",
             'name': 'CL.Benchmark',
             'pathname': '/home/user/test.py',
             'process': 24238,
             'processName': 'MainProcess',
             'relativeCreated': 4951865.670204163,
             'stack_info': None,
             'thread': 140062538003776,
             'threadName': 'MainThread'}
        c = 0
        while True:
            if self.need_to_stop():
                break
            d['msg'] = f"hey {c}"
            t = time.time()
            d['created'] = t
            d['msecs'] = t % 1 * 1000
            level_index = c % len(test_levels)
            d['levelno'] = test_levels[level_index][0]
            d['levelname'] = test_levels[level_index][1]
            r = logging.makeLogRecord(d)
            self.new_record.emit(r)
            c += 1
            time.sleep(CONFIG.benchmark_interval)
