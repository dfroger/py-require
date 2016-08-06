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
This Python module provides a new (unpythonic) approach to loading Python
modules and is completely decoupled from the Python import mechanism.

.. code:: python

  import require
  status = require('./lib/status')
  status.yell()

This is particularly useful in Python applications with a plugin architecture
and solves potential problems when using traditional Python modules that can
easily result in dependency conflicts.
"""

__author__ = 'Niklas Rosenstein <rosensteinniklas(at)gmail.com>'
__version__ = '0.9'

import errno
import functools
import itertools
import marshal
import os
import posixpath
import types
import sys

#: The suffix that is appended to bytecode files.
bcsuffix = 'c@' + sys.version[:3].replace('.', '-')

#: This dictionary maps absolute filenames to the Python modules
#: that are loaded by :func:`require`.
modules = {}

#: A list of global search directories that will always be taken into
#: account when using :func:`require`.
path = []

#: This is a private value that is incremented with each cascade reload
#: to avoid cyclic dependencies resulting in infinite recursion.
_global_cascade_id = 0


class RequireError(ImportError):
  """
  A subclass of :class:`ImportError` that will be raised if :func:`require`
  is unable to find or load a Python module.
  """

error = RequireError


class Context(object):
  """
  Container for contextual information for a module import.

  .. attribute:: path

    List of additional search directories.

  .. attribute:: cascade_reload

    True if a cascade reload was issued when the module was (re-)loaded.
    This will be automatically disabled after the module was finally
    imported.

  .. attribute:: reload_inplace

    True if the current reload procedura should happen inplace.
  """

  def __init__(self, path, reload=False, cascade=False, inplace=False, cascade_id=None):
    self.path = list(path)
    self.cascade_reload = bool(reload and cascade)
    self.reload_inplace = bool(reload and inplace)
    self.cascade_id = cascade_id

  def __repr__(self):
    return 'Context(%r, %r, %r, %r)' % (
      self.path, self.cascade_reload, self.reload_inplace, self.cascade_id)


def require(file, directory=None, path=(), reload=False, cascade=False, inplace=False, get_exports=True):
  """
  Loads a Python module by filename. If *file* is a relative path starting
  with `./`, it will be loaded relative to *directory*. Otherwise, if it
  is not an absolute path, it will be searched in the search *path*. Note
  that *file* should be a UNIX-style path on every platform.

  The algorithm will check the following forms of *file*:

  - `<file>`
  - `<file>c@x-y`
  - `<file>/__init__.py`
  - `<file>/__init__.pyc@x-y`
  - `<file>.py`
  - `<file>.pyc@x-y`

  `c@x-y` is the suffix of bytecode files for the current Python version.


  __Parameters__

  :param file: The name of the Python module to load.
  :param directory: The directory to load a local module from. If omitted,
    will be determined automatically from the caller's global scope using
    :func:`sys._getframe`.
  :param path: A list of additional search paths to search for relative
    modules. This path is considered before `require.path`.
  :param reload: True to force reload the module.
  :param cascade: If *reload* is True, passing True causes a cascade
    reload.
  :param inplace: If *reload* is True, modules will be reloaded in-place
    instead of creating a new module object.
  :param get_exports: Return the `exports` member of the module if there
    is any. False can be passed to always get the actual module object. Can
    also be callable that is passed the module object. The result of this
    callable is returned.
  :return: A :class:`types.ModuleType` object, unless the module has a
    member called `exports`, in which case the value of this member will be
    returned.
  :raise RequireError: If the module could not be found or loaded.
  """

  global _global_cascade_id

  if get_exports is True:
    get_exports = _get_exports
  elif get_exports is False:
    get_exports = lambda mod: mod
  elif not callable(get_exports):
    raise TypeError("get_exports must be callable, True or False")

  # Increase the cascade ID if cascading is requested explicitly.
  if reload and cascade:
    _global_cascade_id += 1

  # file must be a UNIX-style path always. Convert it to the current
  # filesystem's format.
  file = _unix_to_ospath(file)

  # Read the context information from the caller.
  frame = sys._getframe(1).f_globals
  context = frame.get('__require_context__', None)
  if isinstance(context, Context) and context.cascade_reload:
    reload = True
    cascade = True
    inplace = context.reload_inplace
  if isinstance(context, Context):
    path = list(path)
    path.extend(context.path)

  # If no local directory was supplied, use the calling script's parent
  # directory to load relative modules from.
  if not directory and '__file__' in frame:
    # Determine the directory to load the module from the callers
    # global __file__ variable.
    directory = os.path.abspath(os.path.dirname(frame['__file__']))
  elif not directory:
    directory = os.getcwd()

  # If we're in a cascading reload, we have to allocate a new ID.
  cascade_id = context.cascade_id if context else None
  if reload and cascade and cascade_id is None:
    cascade_id = _global_cascade_id

  # Find the best matching file that we can import.
  load_file = _get_best_candidate(file, directory, path)
  if not load_file:
    raise RequireError(file)

  # Check if we already loaded this module and return it preemptively.
  mod = modules.get(load_file)
  if mod and not reload:
    return get_exports(mod)
  if mod and reload and cascade:
    # Check if we're in the same cascading load process.
    if mod.__require_context__.cascade_id == _global_cascade_id:
      return get_exports(mod)

  # The filename and file type that we're ultimately going to load
  # depends on the availability of the cache.
  fullname = load_file
  mode = 'source'
  if load_file.endswith(bcsuffix):
    load_file = load_file[:-len(bcsuffix)]
    mode = 'bytecode'

  # Create the module context information.
  context = Context(path, reload, cascade, inplace, cascade_id)

  # Create and initialize the new module.
  if not (mod and reload and inplace):
    mod = types.ModuleType(load_file)
  mod.__file__ = fullname
  mod.__require_context__ = context
  mod.require = require
  modules[load_file] = mod

  # Load and execute the module code.
  try:
    if mode == 'source':
      with open(fullname, 'r') as fp:
        code = compile(_preprocess_source(fp.read()), fullname, 'exec')
    elif mode == 'bytecode':
      with open(fullname, 'rb') as fp:
        code = marshal.load(fp)
    else:
      assert False
    exec(code, mod.__dict__)
  except BaseException:

    # If anything bad happened, remove the module from the global
    # module cache again. Just be nice and tolerant and allow the
    # module to have been removed already.
    modules.pop(load_file, None)
    raise

  # Write the bytecode cache, but don't be cocky if it doesn't work.
  if not sys.dont_write_bytecode:
    cache_dirname = os.path.dirname(load_file)
    try:
      if not os.path.isdir(cache_dirname):
        os.makedirs(cache_dirname)
      with open(load_file + bcsuffix, 'wb') as fp:
        marshal.dump(code, fp)
    except (OSError, IOError):
      pass

  return get_exports(mod)


def _get_best_candidate(file, main_dir, search_path):
  """
  Finds the best candidate that we can load for the specified *file*
  parameter. The returned string can contain or not contain the bytecode
  suffix :data:`bcsuffix`.
  """

  for dirname in itertools.chain([main_dir], path, search_path):
    quit = False
    curr = file

    # Check special cases: local path or full path, only one test.
    if file.startswith(os.curdir):
      if main_dir is None:
        return None
      quit = True
      curr = os.path.abspath(os.path.normpath(os.path.join(main_dir, curr)))
    elif os.path.isabs(curr):
      quit = True
    elif dirname == main_dir:
      # Otherwise skip checking the main_dir.
      continue
    else:
      curr = os.path.abspath(os.path.join(dirname, curr))

    # Test file choices: as-is, as-bytecode, as __init__.py, -as-bytecode
    if os.path.isfile(curr):
      return curr
    elif os.path.isfile(curr + bcsuffix):
      return curr + bcsuffix  # use existing cache file
    elif os.path.isdir(curr):
      temp = os.path.join(curr, '__init__.py')
      if not os.path.isfile(temp):
        temp += bcsuffix  # check existing cache file
      if os.path.isfile(temp):
        return temp

    if quit:
      break  # We don't need to do this again if the file is absolute

  if not file.endswith('.py'):
    # Try again with .py suffix.
    return _get_best_candidate(file + '.py', main_dir, path)

  return None


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


def _get_exports(mod):
  """
  Helper function that either returns *mod* or ``mod.exports`` if the
  object has that attribute.
  """

  if hasattr(mod, 'exports'):
    return mod.exports
  return mod


def _unix_to_ospath(path):
  parts = path.split(posixpath.sep)
  parts = [posixpath.curdir if x == os.curdir else
           posixpath.pardir if x == os.pardir else x
           for x in parts]
  return os.sep.join(parts)


class _require_module_type(types.ModuleType):
  " Wrapper for the ``module`` object to make it callable. "

  def __init__(self, original_module):
    for key, value in vars(original_module).items():
      setattr(self, key, value)
    self.__original__ = original_module

  @functools.wraps(require)
  def __call__(self, *args, **kwargs):
    return self.require(*args, **kwargs)


if __name__ in sys.modules:
  sys.modules[__name__] = _require_module_type(sys.modules[__name__])
