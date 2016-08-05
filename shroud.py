# Copyright (c) 2016  Niklas Rosenstein
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""
Shroud allows you to load Python modules in a `require()` style.

.. code-block:: python

  from shroud import require, RequireError
  status = require('lib/status')
  try:
    quo = require('lib/quo')
  except RequireError:
    print("lib/quo could not be loaded")

This is particularly useful in Python applications with a plugin architecture
and solves potential problems when using traditional Python modules that can
easily result into dependency conflicts.
"""

__author__ = 'Niklas Rosenstein <rosensteinniklas(at)gmail.com>'
__version__ = '0.1.dev'

import errno
import marshal
import os
import types
import sys

#: This dictionary maps absolute filenames to the Python module
#: that are loaded by :func:`require`.
modules = {}


class RequireError(ImportError):
  """
  A subclass of :class:`ImportError` that will be raised if :func:`require`
  is unable to find or load a Python module.
  """


def require(path, directory=None):
  """
  Loads a Python module by filename. Can fall back to bytecode cache file
  if available and writes them if ``sys.dont_write_bytecode`` is not enabled.

  :param: The path to the Python module. If it contains the ``.py`` suffix,
    the Python module must but a file, otherwise it can also be a directory
    of which the ``__init__.py`` file is loaded.
  :param directory: The directory to consider *path* relative to. If omitted,
    it will be read from the calling stackframe's globals.
  :return: :class:`types.ModuleType`
  """

  frame = sys._getframe(1).f_globals
  if not directory:
    # Determine the directory to load the module from the callers
    # global __file__ variable.
    caller_file = frame.get('__shroud_source__') or frame.get('__file__')
    if not caller_file:
      raise RuntimeError('require() caller must provide __file__ variable')
    directory = os.path.abspath(os.path.dirname(caller_file))

  if not os.path.isabs(path):
    path = os.path.join(directory, path)
  path = os.path.normpath(os.path.abspath(path))

  # Automatically append the .py suffix or load __init__.py if the path
  # points to a directory.
  if os.path.isdir(path):
    path = os.path.join(path, '__init__.py')
  elif not path.endswith('.py'):
    path += '.py'

  # Check if we already loaded this module and return it preemptively.
  mod = modules.get(path)
  if mod:
    return mod

  # The filename and file type that we're ultimately going to load
  # depends on the availability of the cache.
  filename = path
  mode = 'source'

  # Determine the cache path and if either of the source or cache
  # files exist and which we should load.
  bc_path = path + 'c@' + sys.version[:3]
  bc_mod = _getmtime_or_none(bc_path)
  path_mod = _getmtime_or_none(path)
  if path_mod is None and bc_mod is None:
    raise RequireError(path)  # Neither of the two files exist
  elif path_mod is not None and bc_mod is not None:
    if path_mod <= bc_mod:
      # We can load the cache since the source hasn't been touched since.
      filename = bc_path
      mode = 'bytecode'
  elif path_mod is None:
    filename = bc_path
    mode = 'bytecode'

  # Create and initialize the new module.
  mod = types.ModuleType(path)
  mod.__file__ = filename
  mod.__shroud_source__ = path              # Used to determine the correct parent directory on subsequent require() calls
  mod.require = require
  modules[path] = mod

  # Load and execute the module code.
  try:
    if mode == 'source':
      with open(filename, 'r') as fp:
        code = compile(_preprocess_source(fp.read()), filename, 'exec')
    elif mode == 'bytecode':
      with open(filename, 'rb') as fp:
        code = marshal.load(fp)
    else:
      assert False
    exec(code, mod.__dict__)
  except BaseException:
    # If anything bad happened, remove the module from the global
    # module cache again. Just be nice and tolerant and allow the
    # module to have been removed already.
    modules.pop(path, None)
    raise

  # Write the bytecode cache, but don't be cocky if it doesn't work.
  if not sys.dont_write_bytecode:
    cache_dirname = os.path.dirname(bc_path)
    try:
      if not os.path.isdir(cache_dirname):
        os.makedirs(cache_dirname)
      with open(bc_path, 'wb') as fp:
        marshal.dump(code, fp)
    except (OSError, IOError):
      pass

  return mod


def _preprocess_source(source):
  """
  This method is called when a Python module is loaded from source
  right before it is compiled into a code object.
  """

  if sys.version_info[0] == 2:
    # We have to add this line for Python 2 sources as we have no
    # valid module name and otherwise we get RuntimeWarnings.
    source = 'from __future__ import absolute_import;' + source
  return source


def _getmtime_or_none(filename):
  """
  Returns the file modification time of *path* or None if the path
  doesn't exist.
  """

  try:
    return os.path.getmtime(filename)
  except (OSError, IOError) as exc:
    if exc.errno == errno.ENOENT:
      return None
    raise


__all__ = ['require', 'RequireError']


if __name__ == "__main__":
  # Fill in the shroud module to avoid it being imported (again)
  # which can cause modules to be loaded two times.
  sys.modules['shroud'] = sys.modules[__name__]
