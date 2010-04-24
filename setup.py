#! /usr/bin/env python

from distutils.core import setup

setup(name = 'doit',
      description = 'doit - Automation Tool',
      version = '0.8.dev',
      license = 'MIT',
      author = 'Eduardo Naufel Schettino',
      author_email = 'schettino72@gmail.com',
      url = 'http://python-doit.sourceforge.net/',
      classifiers = ['Development Status :: 4 - Beta',
                     'Environment :: Console',
                     'Intended Audience :: Developers',
                     'Intended Audience :: System Administrators',
                     'License :: OSI Approved :: MIT License',
                     'Natural Language :: English',
                     'Operating System :: OS Independent',
                     'Operating System :: POSIX',
                     'Programming Language :: Python :: 2.4',
                     'Programming Language :: Python :: 2.5',
                     'Programming Language :: Python :: 2.6',
                     'Topic :: Software Development :: Build Tools',
                     'Topic :: Software Development :: Testing',
                     'Topic :: Software Development :: Quality Assurance',
                     ],

      packages = ['doit'],
      scripts = ['bin/doit'],
      install_requires = ['pyinotify'],

      long_description = """
doit comes from the idea of bringing the power of build-tools to execute any kind of task. It will keep track of dependencies between "tasks" and execute them only when necessary. It was designed to be easy to use and "get out of your way".

`doit` can be used as:

 * a build tool (generic and flexible)
 * home of your management scripts (it helps you organize and combine shell scripts and python scripts)
 * a functional tests runner (combine together different tools)
"""
      )

