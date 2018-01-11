# cutelog - GUI for Python's logging module

This is a graphical log viewer for Python's standard logging module.
It can be targeted as a SocketHandler with no additional setup (see [Usage](#usage)).

The program is in beta: it's lacking some features and may be unstable, but it works.
cutelog is cross-platform, although it's mainly written and optimized for Linux.

This is my first released project, so the code is by no means stellar.
Feedback and contributions are appreciated!

## Features
* Allows any number of simultaneous connections
* Fully customizable look of log levels and columns
* Filtering based on level and name of the logger, as well as filtering by searching
* Search through all records or only through filtered ones
* View exception tracebacks or messages in a separate window
* Dark theme (with its own set of colors for levels)
* Pop tabs out of the window, merge records of multiple tabs into one

## Screenshots
Light theme | Dark theme
------------|-----------
<img src="https://raw.githubusercontent.com/busimus/cutelog/master/screenshots/main_light.png" width="240"> | <img src="https://raw.githubusercontent.com/busimus/cutelog/master/screenshots/main_dark.png" width="240">

## Installation
**If you're using Linux**, install PyQt5 from your package manager before installing cutelog (package name is probably ``python3-pyqt5`` or ``python-pyqt5``). Or just run ``pip install pyqt5`` to install it from pip, which is sub-optimal.

```
$ pip install cutelog
```
Or install the latest development version from the source:

```
$ pip install git+https://github.com/busimus/cutelog.git
```

### Requirements
* Python 3.6 (or newer)
* PyQt5

## Usage
1. Start `cutelog`
2. Put the following into your code:
```python
import logging
import logging.handlers

log = logging.getLogger('MyLogger')
log.setLevel(1)  # to send all messages to cutelog
socket_handler = logging.handlers.SocketHandler('127.0.0.1', 19996)  # default listening address
log.addHandler(socket_handler)
log.info('Hello world!')
```

## Planned features
* [ ] Presets for colors
* [ ] Indication that the connection has been closed
* [ ] Presets for the logger header
* [ ] Modify how rows are arranged in the detail table (like the header dialog)
* [ ] Improve the way existence of an exception is shown
* [ ] Fix double-search on the last matched result (or indicate that the last result was reached)
* [ ] Ability to save and load logs
* [ ] Alarms/notifications triggered by specified messages
* [ ] Figure out how to search up
* [ ] Option to merge multiple connections without stopping them

### Code improvements:
* [ ] Proper exception handling in critical places
* [ ] Message boxes for errors to avoid relying on CLI logging
* [ ] Ability to ignore resources.py and instead use actual files for quick stylesheet reload, etc.

### Dreams, uncertainties, and low priority improvements:
* [ ] Rewrite all/most UIs in code instead of using Qt Designer
* [ ] Switch to [qtawesome](https://github.com/spyder-ide/qtawesome) instead of ion-icons?
* [ ] Support for custom themes?
* [ ] Rewrite the server with robust architecture and additional transports and serializers (e.g. ZeroMQ, WebSockets; msgpack)?
* [ ] Ditch asyncio if/when [curio](https://github.com/dabeaz/curio) takes off?
* [ ] Or rewrite the whole thing in C++ and make it be a generic logging receiver not just for Python???


## Attributions
Free software used:
* [PyQt5](https://riverbankcomputing.com/software/pyqt/intro) - GPLv3 License, Copyright (c) 2017 Riverbank Computing Limited <info@riverbankcomputing.com>
* [ion-icons](https://github.com/ionic-team/ionicons) - MIT License, Copyright (c) 2016 Drifty (http://drifty.com/)

And thanks to [logview](https://pythonhosted.org/logview/) by Vinay Sajip for UI inspiration.

### Copyright and license
Copyright (C) 2018, Alexander Bus

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
