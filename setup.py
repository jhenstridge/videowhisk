#!/usr/bin/env python3

from setuptools import setup

setup(
    name="videowhisk",
    version="0.1",
    author="James Henstridge",
    author_email="james@jamesh.id.au",
    packages=[
        "videowhisk",
    ],
    install_requires=[
        "PyGObject",
        "asyncio-glib",
    ],
    test_suite="tests",
)
