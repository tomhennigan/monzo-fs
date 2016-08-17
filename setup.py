#!/usr/bin/env python

from setuptools import setup

setup(name='mondo-fs',
     version='0.1.2',
     description='A FUSE file system for Mondo bank.',
     author='Tom Hennigan',
     author_email='tomhennigan@gmail.com',
     license='Apache 2.0',
     url='https://github.com/tomhennigan/mondo-fs',
     classifiers=['Development Status :: 3 - Alpha',
                   'Intended Audience :: Developers',
                   'Programming Language :: Python :: 2',
                   'Programming Language :: Python :: 2.7',
                   ],
    entry_points={
        'console_scripts': [
            'mondo-fs = mondofs.__main__:main',
        ],
    },
    packages=['mondofs'],
    include_package_data=True,
    install_requires=['requests',
                      'fusepy>=2.0.4',
                      'rfc3339',
                      'iso8601'])
