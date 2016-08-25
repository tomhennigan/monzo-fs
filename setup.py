#!/usr/bin/env python

import setuptools

setuptools.setup(
     name='monzo-fs',
     version='0.1.3',
     description='A FUSE file system for Mondo bank.',
     author='Tom Hennigan',
     author_email='tomhennigan@gmail.com',
     license='Apache 2.0',
     url='https://github.com/tomhennigan/monzo-fs',
     classifiers=['Development Status :: 3 - Alpha',
                   'Intended Audience :: Developers',
                   'Programming Language :: Python :: 2',
                   'Programming Language :: Python :: 2.7',
                   ],
    entry_points={
        'console_scripts': [
            'monzo-fs = monzo_fs.__main__:main',
        ],
    },
    packages=setuptools.find_packages(),
    include_package_data=True,
    install_requires=['requests',
                      'fusepy>=2.0.4',
                      'rfc3339',
                      'iso8601'])
