import json
import pickle
import struct
import time

from qtpy.QtCore import QThread, Signal
from qtpy.QtNetwork import QHostAddress, QTcpServer, QTcpSocket

from .config import CONFIG, MSGPACK_SUPPORT, CBOR_SUPPORT
from .logger_tab import LogRecord
from .utils import show_critical_dialog


class LogServer(QTcpServer):
    def __init__(self, main_window, on_connection, log):
        super().__init__(main_window)
        self.log = log.getChild('TCP')

        self.log.info('Initializing')

        self.main_window = main_window
        self.on_connection = on_connection

        self.host, self.port = CONFIG.listen_address
        self.host = QHostAddress(self.host)
        self.benchmark = CONFIG['benchmark']
        self.conn_count = 0

        self.threads = []

    def start(self):
        self.log.info('Starting the server')
        if self.benchmark:
            self.log.debug('Starting a benchmark connection')
            new_conn = BenchmarkConnection(self, None, "benchmark", self.log)
            new_conn.finished.connect(new_conn.deleteLater)
            new_conn.connection_finished.connect(self.cleanup_connection)
            self.on_connection(new_conn, -1)
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
        self.conn_count += 1
        conn_id = str(self.conn_count)
        self.log.info('New connection id={}'.format(conn_id))
        new_conn = LogConnection(self, socketDescriptor, conn_id, self.log)

        self.on_connection(new_conn, conn_id)
        new_conn.setObjectName(conn_id)
        new_conn.finished.connect(new_conn.deleteLater)
        new_conn.connection_finished.connect(self.cleanup_connection)
        new_conn.start()
        self.threads.append(new_conn)

    def close_server(self):
        self.log.debug('Closing the server')
        self.main_window.set_status('Stopping the server...')
        self.close()
        for thread in self.threads.copy():
            thread.requestInterruption()
        self.wait_connections_stopped()
        self.main_window.set_status('Server has stopped')

    def wait_connections_stopped(self):
        self.log.debug('Waiting for {} connections threads to stop'.format(len(self.threads)))
        for thread in self.threads.copy():
            try:
                if not thread.wait(1500):
                    # @Hmm: sometimes wait() complains about QThread waiting on itself
                    self.log.debug("Thread \"{}\" didn't stop in time, exiting".format(thread))
                    return
            except RuntimeError:  # happens when thread has been deleted before we got to it
                self.log.debug('Thread {} has been deleted already'.format(thread))
        self.log.debug('Waiting for connections has stopped')

    def cleanup_connection(self, connection):
        try:
            self.threads.remove(connection)
        except Exception:
            self.log.error('Double delete on connection: {}'.format(connection), exc_info=True)
            return


class LogConnection(QThread):

    new_record = Signal(LogRecord)
    connection_finished = Signal(object)
    internal_prefix = b"!!cutelog!!"

    def __init__(self, parent, socketDescriptor, conn_id, log):
        super().__init__(parent)
        self.log = log.getChild(conn_id)
        self.socketDescriptor = socketDescriptor
        self.conn_id = conn_id
        self.tab_closed = False  # used to stop the connection from a "parent" logger
        self.setup_serializers()

    def __repr__(self):
        return "{}(id={})".format(self.__class__.__name__, self.conn_id)

    def setup_serializers(self):
        self.serializers = {'pickle': pickle.loads, 'json': json.loads}
        if MSGPACK_SUPPORT:
            import msgpack
            from functools import partial
            self.serializers['msgpack'] = partial(msgpack.loads, raw=False)
        if CBOR_SUPPORT:
            import cbor
            self.serializers['cbor'] = cbor.loads
        self.deserialize = self.serializers[CONFIG['default_serialization_format']]

    def run(self):
        self.log.debug('Connection id={} is starting'.format(self.conn_id))

        def wait_and_read(n_bytes):
            """
            Convenience function that simplifies reading and checking for stop events, etc.
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
                if self.need_to_stop():
                    return None
                new_data = sock.read(n_bytes - len(data))
                if type(new_data) != bytes:
                    new_data = new_data.data()
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

            if data.startswith(self.internal_prefix):
                self.handle_internal_command(data)
                continue

            try:
                logDict = self.deserialize(data)
                record = LogRecord(logDict)
            except Exception:
                self.log.error('Creating log record failed', exc_info=True)
                continue
            self.new_record.emit(record)

        self.log.debug('Connection id={} is stopping'.format(self.conn_id))
        sock.disconnectFromHost()
        sock.close()
        self.connection_finished.emit(self)
        self.log.debug('Connection id={} has stopped'.format(self.conn_id))

    def need_to_stop(self):
        return any([self.tab_closed, self.isInterruptionRequested()])

    def handle_internal_command(self, data):
        """
        Used for managing listener options from non-Python clients.
        Command data must start with a special prefix (see self.internal_prefix),
        followed by a command in a key=value format.

        Supported commands:
            format - changes the serialization format to one specified in
                     self.serializers[value]. pickle and json are supported out of the box
                     Example: format=json
        """
        try:
            data = data[len(self.internal_prefix):].decode('utf-8')
            cmd, value = data.split("=", 1)
        except Exception:
            self.log.error('Internal request decoding failed', exc_info=True)
            return
        self.log.debug('Handling internal cmd="{}", value="{}"'.format(cmd, value))
        if cmd == 'format':
            if value in self.serializers:
                self.log.debug('Changing serialization format to "{}"'.format(value))
                self.deserialize = self.serializers[value]
            else:
                self.log.error('Serialization format "{}" is not supported'.format(value))


class BenchmarkConnection(LogConnection):

    def run(self):
        import random
        test_levels = [(10, 'DEBUG'), (20, 'INFO'), (30, 'WARNING'),
                       (40, 'ERROR'), (50, 'CRITICAL'), (21, 'REQ')]
        test_names = ['CL', 'CL.Test1', 'CL.Test1.Test2', 'CL.Test3'
                      'hey', 'hey.hi.hello', 'CL.Test3.Test4.Test5']
        # dummy log item
        d = {'args': None,
             'created': 0,
             'exc_info': None,
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
        d = {}
        c = 0
        while True:
            if self.need_to_stop():
                break
            dd = d.copy()
            dd['msg'] = "msg {}".format(c)
            dd['name'] = random.choice(test_names)
            t = time.time()
            dd['created'] = t
            level_index = c % len(test_levels)
            dd['levelname'] = test_levels[level_index][1]
            if dd['levelname'] == "CRITICAL":
                dd['exc_text'] = 'exception test'

            for i in range(random.randrange(6)):
                dd[str(i) + "f"] = random.randrange(256)
            r = LogRecord(dd)
            self.new_record.emit(r)
            c += 1
            time.sleep(CONFIG.benchmark_interval)
        self.connection_finished.emit(self)
        self.log.debug('Connection id={} has stopped'.format(self.conn_id))


class BenchmarkMonitor(QThread):
    speed_readout = Signal(str)

    def __init__(self, main_window, logger):
        super().__init__(main_window)
        self.logger = logger

    def run(self):
        import time
        readouts = []
        while True:
            if self.isInterruptionRequested():
                break
            time.sleep(0.5)
            readouts.append(self.logger.monitor_count)
            average = int(sum(readouts) / len(readouts)) * 2
            status = "{} rows/s, average: {} rows/s".format(self.logger.monitor_count * 2, average)
            if self.logger.monitor_count == 0:
                continue
            self.speed_readout.emit(status)
            print(status, average)
            self.logger.monitor_count = 0
        print('Result:', int(sum(readouts) / len(readouts)) * 2, 'average')
