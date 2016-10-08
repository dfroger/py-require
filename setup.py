
import os, sys
from setuptools import setup

def restify():
  if os.path.isfile('README.md'):
    if os.system('pandoc -s README.md -o README.rst') != 0:
      print('-----------------------------------------------------------')
      print('WARNING: pandoc command failed, could not restify README.md')
      print('-----------------------------------------------------------')
      if sys.stdout.isatty():
        input("Enter to continue... ")
  with open('README.rst') as fp:
    return fp.read()

setup(
  name = "py-require",
  version = "0.17",
  description = "require() for Python",
  long_description = restify(),
  author = "Niklas Rosenstein",
  author_email = "rosensteinniklas@gmail.com",
  url = "https://github.com/NiklasRosenstein/py-require",
  py_modules = ['require'],
  keywords = ['require', 'importer', 'loader'],
  classifiers = [
    'Development Status :: 4 - Beta',
    'Environment :: Other Environment',
    'Environment :: Plugins',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python',
    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: Implementation :: CPython',
    'Programming Language :: Python :: Implementation :: Jython',
    'Programming Language :: Python :: Implementation :: PyPy',
    'Topic :: Software Development :: Libraries :: Python Modules',
    'Topic :: Utilities'
  ]
)
