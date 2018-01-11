.. contents:: Table of contents
   :depth: 2

=======
cutelog
=======

This is a graphical log viewer for Python's standard logging module.
It can be targeted as a SocketHandler with no additional setup (see Usage_).

The program is in beta: it's lacking some features and may be unstable, but it works.
cutelog is cross-platform, although it's mainly written and optimized for Linux.

This is my first released project, so the code is by no means stellar.
Feedback and contributions are appreciated!

Features
========
* Allows any number of simultaneous connections
* Fully customizable look of log levels and columns
* Filtering based on level and name of the logger, as well as filtering by searching
* Search through all records or only through filtered ones
* View exception tracebacks or messages in a separate window
* Dark theme (with its own set of colors for levels)
* Pop tabs out of the window, merge records of multiple tabs into one


Installation
============
**If you're using Linux**, install PyQt5 from your package manager before installing cutelog (package name is probably ``python3-pyqt5`` or ``python-pyqt5``). Or just run ``pip install pyqt5`` to install it from pip, which is sub-optimal.
::

    $ pip install --upgrade cutelog

Or install the latest development version from the source::

    $ pip install git+https://github.com/busimus/cutelog.git

Requirements
------------
* Python 3.6 (or newer)
* PyQt5

Usage
=====
1. Start `cutelog`

2. Put the following into your code:

.. code-block :: python

    import logging
    from logging.handlers import SocketHandler

    log = logging.getLogger('MyLogger')
    log.setLevel(1)  # to send all messages to cutelog
    socket_handler = SocketHandler('127.0.0.1', 19996)  # default listening address
    log.addHandler(socket_handler)
    log.info('Hello world!')

Code, issues, changelog
=======================
Visit the project's `GitHub page <https://github.com/busimus/cutelog>`_.
