.. contents:: Table of contents
   :depth: 2

=======
cutelog
=======

This is a graphical log viewer for Python's standard logging module.
It can be targeted with a SocketHandler with no additional setup (see Usage_).
cutelog is cross-platform, although it's mainly written and optimized for Linux.

Features
========
* Allows any number of simultaneous connections
* Customizable look of log levels and columns, with presets for each
* Filtering based on level and namespace, as well as filtering by searching
* Search through all records or only through filtered ones
* Display extra fields under the message with `Extra mode <https://github.com/busimus/cutelog/wiki/Creating-a-client-for-cutelog#extra-mode>`_
* View exception tracebacks or messages in a separate window
* Dark theme (with its own set of colors for levels)
* Pop tabs out of the window, merge records of multiple tabs into one
* Save/load records to/from a file in JSON format

Installation
============
**If you're using Linux**, install PyQt5 (or PySide2) from your package manager before installing cutelog (package name is probably ``python3-pyqt5`` or ``python-pyqt5``). Or just run ``pip install pyqt5`` to install it from pip, which is sub-optimal.
::

    $ pip install --upgrade cutelog

Or install the latest development version from the source::

    $ pip install git+https://github.com/busimus/cutelog.git

Requirements
------------
* Python 3.5 (or newer)
* PyQt5 (preferably 5.6 or newer) or PySide2
* QtPy

Usage
=====
1. Start `cutelog`

2. Put the following into your code:

.. code-block :: python

    import logging
    from logging.handlers import SocketHandler

    log = logging.getLogger('Root logger')
    log.setLevel(1)  # to send all messages to cutelog
    socket_handler = SocketHandler('127.0.0.1', 19996)  # default listening address
    log.addHandler(socket_handler)
    log.info('Hello world!')

Afterwards it's recommended to designate different loggers for different parts of your program with `log_2 = log.getChild("Child logger")`.
This will create "log namespaces" which allow you to filter out messages from various subsystems of your program.

Code, issues, changelog
=======================
Visit the project's `GitHub page <https://github.com/busimus/cutelog>`_.
