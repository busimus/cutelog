# -*- coding: utf-8 -*-

from os.path import dirname, join
from setuptools import setup


VERSION = '1.0.3'


# def build_qt_resources():
#     from PyQt5 import pyrcc_main
#     pyrcc_main.processResourceFile(['cutelog/styles/dark_theme.qrc'], 'cutelog/resources.py', False)


setup(
    name="cutelog",
    version=VERSION,
    description="GUI for Python's logging module",
    packages=["cutelog"],

    author="Alexander Bus",
    author_email="busfromrus@gmail.com",
    url="https://github.com/busimus/cutelog/",

    requires=['PyQt5'],
    python_requires=">=3.6",

    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: X11 Applications :: Qt",
        "Environment :: MacOS X :: Cocoa",
        "Environment :: Win32 (MS Windows)",
        "Framework :: AsyncIO",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: System :: Logging",
        "Topic :: System :: Monitoring",
    ],
    download_url="https://github.com/Busimus/cutelog/archive/{}.zip".format(VERSION),
    entry_points={'console_scripts': 'cutelog=cutelog.__main__:main'},
    include_package_data=True,
    install_requires=['PyQt5;platform_system=="Darwin"',    # it's better to use distro-supplied
                      'PyQt5;platform_system=="Windows"'],  # PyQt package on Linux
    keywords=["log", "logging", "gui", "qt"],
    license="GPLv3",
    long_description=open(join(dirname(__file__), "README.rst")).read(),
    # package_data={"cutelog": ["styles/*", "ui/*"]}, # everything is in resource.py already
    data_files=[('share/applications', ['share/cutelog.desktop']),
                ('share/pixmaps', ['share/cutelog.png'])],
    zip_safe=False,
)
