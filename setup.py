# -*- coding: utf-8 -*-

from os.path import dirname, join

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.install import install

VERSION = '2.0.6'


def build_qt_resources():
    print('Compiling resources...')
    try:
        from PyQt5 import pyrcc_main
    except ImportError as e:
        raise Exception("Building from source requires PyQt5") from e
    pyrcc_main.processResourceFile(['cutelog/resources/resources.qrc'],
                                   'cutelog/resources.py', False)
    # Rewrite PyQt5 import statements to qtpy
    with open('cutelog/resources.py', 'r') as rf:
        lines = rf.readlines()
        for i, line in enumerate(lines):
            if 'import' in line and not line.startswith('\\x'):
                new_line = line.replace('PyQt5', 'qtpy')
                lines[i] = new_line
    with open('cutelog/resources.py', 'w') as wf:
        wf.writelines(lines)
    print('Resources compiled successfully')


class CustomInstall(install):
    def run(self):
        try:
            build_qt_resources()
        except Exception as e:
            print('Could not compile the resources.py file due to an exception: "{}"\n'
                  'Aborting build.'.format(e))
            raise
        install.run(self)


class CustomBuild(build_py):
    def run(self):
        try:
            build_qt_resources()
        except Exception as e:
            print('Could not compile the resources.py file due to an exception: "{}"\n'
                  'Aborting build.'.format(e))
            raise
        build_py.run(self)


setup(
    name="cutelog",
    version=VERSION,
    description="GUI for Python's logging module",
    packages=["cutelog"],

    author="Alexander Bus",
    author_email="busfromrus@gmail.com",
    url="https://github.com/busimus/cutelog/",

    python_requires=">=3.5",
    install_requires=['PyQt5;platform_system=="Darwin"',  # it's better to use distro-supplied
                      'PyQt5;platform_system=="Windows"',  # PyQt package on Linux
                      'QtPy'],

    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: X11 Applications :: Qt",
        "Environment :: MacOS X :: Cocoa",
        "Environment :: Win32 (MS Windows)",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: System :: Logging",
        "Topic :: System :: Monitoring",
    ],
    download_url="https://github.com/Busimus/cutelog/archive/{}.zip".format(VERSION),
    entry_points={'console_scripts': 'cutelog=cutelog.__main__:main'},
    include_package_data=True,
    keywords=["log", "logging", "gui", "qt"],
    license="MIT",
    long_description=open(join(dirname(__file__), "README.rst")).read(),
    # package_data={"cutelog": ["styles/*", "ui/*"]}, # everything is in resources.py already
    data_files=[('share/applications', ['share/cutelog.desktop']),
                ('share/pixmaps', ['share/cutelog.png'])],
    zip_safe=False,
    cmdclass=dict(install=CustomInstall, build_py=CustomBuild)
)
