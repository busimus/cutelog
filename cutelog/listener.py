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

        self.threads = []
        self.connections = 0

    def start(self):
        self.log.info('Starting the server')
        if self.benchmark:
            self.log.debug('Starting a benchmark connection')
            new_conn = BenchmarkConnection(self, None, "benchmark", self.stop_signal, self.log)
            new_conn.finished.connect(new_conn.deleteLater)
            new_conn.connection_finished.connect(self.cleanup_connection)
            self.on_connection(new_conn, "benchmark")
            self.threads.append(new_conn)
            new_conn.start()

        result = self.listen(self.host, self.port)
        if not result:
            err_string = self.errorString()
            show_critical_dialog(self.main_window, 'Error while starting the server', err_string)
        else:
            address = "{}:{}".format(self.host.toString(), self.port)
            self.main_window.set_status('Server is listening on {}...'.format(address))

    def incomingConnection(self, socketDescriptor):
        self.connections += 1
        name = 'Logger {}'.format(self.connections)
        self.log.info('New connection: "{}"'.format(name))
        new_conn = LogConnection(self, socketDescriptor, name, self.stop_signal, self.log)

        self.on_connection(new_conn, name)
        new_conn.finished.connect(new_conn.deleteLater)
        new_conn.connection_finished.connect(self.cleanup_connection)
        new_conn.start()
        self.threads.append(new_conn)

    def close_server(self, wait=True):
        self.log.debug('Closing the server')
        self.main_window.set_status('Stopping the server...')
        self.close()
        if wait:
            self.wait_connections_stopped()
        self.main_window.set_status('Server has stopped')

    def wait_connections_stopped(self):
        self.log.debug('Waiting for {} connections threads to stop'.format(len(self.threads)))
        to_wait = self.threads.copy()  # to protect against changes during iteration
        for thread in to_wait:
            try:
                if not thread.wait(1000):
                    self.log.error('Thread "{}" didn\'t stop in time, terminating'.format(thread))
                    thread.terminate()
                    self.log.error('Thread "{}" terminated'.format(thread))
            except RuntimeError:  # happens when thread has been deleted before we got to it
                self.log.debug('Thread {} has been deleted already'.format(thread))
        self.log.debug('All connections stopped')

    def cleanup_connection(self, connection):
        try:
            self.threads.remove(connection)
        except Exception as e:
            self.log.error('Double delete on connection: {}'.format(connection), exc_info=True)
            # import pdb; pdb.set_trace()


class LogConnection(QThread):

    new_record = pyqtSignal(logging.LogRecord)
    connection_finished = pyqtSignal(object)

    def __init__(self, parent, socketDescriptor, name, stop_signal, log):
        super().__init__(parent)
        self.log = log.getChild(name)
        self.socketDescriptor = socketDescriptor
        self.name = name
        self.stop_signal = stop_signal
        self.tab_closed = False  # used to stop the connection from a "parent" logger

    def __repr__(self):
        # return "{}(name={}, socketDescriptor={})".format(self.__class__.__name__, self.name,
        #                                                  self.socketDescriptor)
        return "{}(name={})".format(self.__class__.__name__, self.name)

    def run(self):
        self.log.debug('Connection "{}" is starting'.format(self.name))

        def wait_and_read(n_bytes):
            """
            Convinience function that simplifies reading and checking for stop events, etc.
            Returns a byte string of length n_bytes or None if socket needs to be closed.

            """
            data = b""
            while len(data) < n_bytes:
                if sock.bytesAvailable() == 0:
                    new_data = sock.waitForReadyRead(100)  # wait for 100ms between read attempts
                    if not new_data:
                        if sock.state() != sock.ConnectedState or self.need_to_stop():
                            return None
                        else:
                            continue
                new_data = sock.read(n_bytes - len(data))
                data += new_data
            return data

        sock = QTcpSocket(None)
        sock.setSocketDescriptor(self.socketDescriptor)
        sock.waitForConnected()

        while True:
            read_len = wait_and_read(4)
            if not read_len:
                break
            read_len = struct.unpack(">L", read_len)[0]

            data = wait_and_read(read_len)
            if not data:
                break

            try:
                data = pickle.loads(data)
                record = logging.makeLogRecord(data)
            except Exception as e:
                self.log.error('Creating log record failed', exc_info=True)
                continue
            self.new_record.emit(record)

        self.log.debug('Connection "{}" is stopping'.format(self.name))
        sock.disconnectFromHost()
        sock.close()
        self.connection_finished.emit(self)
        self.log.debug('Connection "{}" has stopped'.format(self.name))

    def need_to_stop(self):
        return any([self.stop_signal.is_set(), self.tab_closed])


class BenchmarkConnection(LogConnection):

    def run(self):
        test_levels = [(10, 'DEBUG'), (20, 'INFO'), (30, 'WARNING'),
                       (40, 'ERROR'), (50, 'CRITICAL'), (21, 'REQ')]
        # dummy log item
        d = {'args': None,
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
             'threadName': 'MainThread',
             'extra_column': 'hey there'}
        c = 0
        while True:
            if self.need_to_stop():
                break
            d['msg'] = "hey {}".format(c)
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
        self.connection_finished.emit(self)
        self.log.debug('Connection "{}" has stopped'.format(self.name))
