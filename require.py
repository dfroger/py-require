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

__author__ = 'Niklas Rosenstein <rosensteinniklas(at)gmail.com>'
__version__ = '0.13'

import errno
import itertools
import marshal
import os
import posixpath
import types
import sys

class RequireError(ImportError):
  pass

class RequireModuleContext(object):

  def __init__(self, path, reload, cascade, inplace, cascade_index, parent):
    self.path = list(path)
    self.reload = reload
    self.cascade = cascade if reload else False
    self.inplace = inplace if reload else False
    self.cascade_index = cascade_index
    self.parent = parent

  @property
  def path_all(self):
    result = []
    while self:
      result.append(self.path)
      self = self.parent
    return itertools.chain(*result)

class Require(types.ModuleType):

  error = RequireError

  def __init__(self, path=(), write_bytecode=None, _keep_alive=None):
    super(Require, self).__init__('require')
    self.bytecache_suffix = 'c@' + sys.version[:3].replace('.', '-')
    self.modules = {}
    self.path = list(path)
    self.cascade_index = 0
    self.write_bytecode = write_bytecode
    self._keep_alive = _keep_alive
    if _keep_alive:
      self.Require = Require
      self.__file__ = _keep_alive.__file__

  def require(self, file, directory=None, path=(), reload=False,
              cascade=False, inplace=False, get_exports=True,
              _stackdepth=1):
    """
    Load a Python module from the specified *file*. The loaded file
    will be executed with the ``require()`` function available so it
    can load other modules in return.
    """

    if file == '.' or file == './':
      file = './__init__.py'
    file = self._unix_to_ospath(file)

    if reload and cascade:
      self.cascade_index += 1

    if get_exports is True:
      get_exports = lambda mod: getattr(mod, 'exports', mod)
    elif get_exports is False:
      get_exports = lambda mod: mod
    elif not callable(get_exports):
      raise TypeError("require(): get_exports must be callable, True or False")

    parent_globals = sys._getframe(_stackdepth).f_globals
    parent_context = parent_globals.get('__require_module_context__')
    if isinstance(parent_context, RequireModuleContext):
      # Allow cascading reloads to propagate.
      if parent_context.reload and parent_context.cascade:
        reload = True
        cascade = True
        inplace = parent_context.inplace
    else:
      parent_context = None

    if not directory and '__file__' in parent_globals:
      directory = os.path.dirname(os.path.abspath(parent_globals['__file__']))
    elif not directory:
      directory = os.getcwd()

    cascade_index = parent_context.cascade_index if parent_context else None
    if cascade_index is None and reload and cascade:
      # A new cascade reload is started, use a new cascade index.
      cascade_index = self.cascade_index

    search_path = itertools.chain(path, parent_context.path_all if parent_context else [])
    module_file, real_file = self.find_module(file, directory, search_path)
    if not module_file:
      raise self.error(file)

    # If there is a "real_file" version for the file we should load,
    # we expect the "module_file" to be a bytecache version.
    if real_file:
      mode = 'bytecode'
    else:
      mode = 'source'
      real_file = module_file

    mod = self.modules.get(real_file)
    if not reload and mod is not None:
      return get_exports(mod)
    if reload and cascade and mod is not None:
      # If we're still in the same cascade, don't load the module again.
      if mod.__require_module_context__.cascade_index == cascade_index:
        return get_exports(mod)

    context = RequireModuleContext(path, reload, cascade, inplace,
      cascade_index, parent_context)

    if not (mod is not None and reload and inplace):
      mod = types.ModuleType(real_file)
    mod.__file__ = module_file
    mod.__require_module_context__ = context
    mod.require = self
    self.modules[real_file] = mod

    try:
      code = self._exec_module(mod, module_file, mode)
    except BaseException:
      self.modules.pop(module_file, None)
      raise

    write = self.write_bytecode
    if write is None:
      write = not sys.dont_write_bytecode
    if write:
      try:
        self._write_bytecode(code, real_file + self.bytecache_suffix)
      except (OSError, IOError):
        pass # intentional

    return get_exports(mod)

  def __call__(self, *args, **kwargs):
    """ Alias for ``require()``. """
    kwargs['_stackdepth'] = kwargs.get('_stackdepth', 1) + 1
    return self.require(*args, **kwargs)

  def find_module(self, file, directory, path):
    """
    This function is called to find the actual full filename for the *file*
    parameter to load when using :meth:`require`.

    :param file: The filename passed to :meth:`require`.
    :param directory: The main directory from which relative filenames
      should be loaded. This is either the current working directory or
      the parent directory of the script that calls :meth:`require`.
    :param path: An iterable (not sequence!) of the explicitly passed
      *path* list and inherited search paths from parent :meth:`require`
      calls.
    :return: A tuple of ``(module_file, real_file)`` where the *module_file*
      is the file that will actually be loaded and *real_file* is the name
      of the file in its original source version. If there is no original
      source version (that is, *module_file* is the source file and not a
      bytecache version), it should be None. If the module can not be found,
      ``(None, None)`` should be returned.
    """

    if not isinstance(path, list):
      path = list(path)

    if file.startswith(os.curdir):
      if directory is None:
        return None, None
      file = os.path.abspath(os.path.normpath(os.path.join(directory, file)))
      check_path = [None]
    elif os.path.isabs(file):
      check_path = [None]
    else:
      check_path = path

    for parent_dir in check_path:
      if parent_dir is not None:
        curr = os.path.join(parent_dir, file)
      else:
        curr = file
      bytefile = curr + self.bytecache_suffix
      if os.path.isfile(bytefile):
        if os.path.isfile(curr):
          # Choose the source file if its newer.
          if os.path.getmtime(curr) > os.path.getmtime(bytefile):
            return curr, None
        return bytefile, curr
      elif os.path.isfile(curr):
        return curr, None
      elif not curr.endswith(".py") and os.path.isdir(curr):
        return self.find_module(os.path.join(curr, '__init__.py'), directory, path)

    if not file.endswith(".py"):
      return self.find_module(file + ".py", directory, path)

    return None, None

  @classmethod
  def _exec_module(cls, mod, load_file, mode):
    assert mode in ('source', 'bytecode')
    if mode == 'source':
      with open(load_file, 'r') as fp:
        code = compile(cls._preprocess_source(fp.read()), load_file, 'exec')
    elif mode == 'bytecode':
      with open(load_file, 'rb') as fp:
        code = marshal.load(fp)
    exec(code, mod.__dict__)
    return code

  @staticmethod
  def _write_bytecode(code, filename):
    dirname = os.path.dirname(filename)
    if not os.path.isdir(dirname):
      os.makedirs(dirname)
    with open(filename, 'wb') as fp:
      marshal.dump(code, fp)

  @staticmethod
  def _preprocess_source(source):
    if sys.version_info[0] == 2:
      # We have to add this line for Python 2 sources as we have no
      # valid module name and otherwise we get RuntimeWarnings.
      source = 'from __future__ import absolute_import;' + source
    return source

  @staticmethod
  def _unix_to_ospath(path):
    parts = path.split(posixpath.sep)
    parts = [posixpath.curdir if x == os.curdir else
             posixpath.pardir if x == os.pardir else x
             for x in parts]
    return os.sep.join(parts)

  @staticmethod
  def _getmtime_or_none(filename):
    try:
      return os.path.getmtime(filename)
    except (OSError, IOError) as exc:
      if exc.errno == errno.ENOENT:
        return None
      raise

require = Require(_keep_alive=sys.modules.get(__name__))

if __name__ in sys.modules and globals() is vars(sys.modules[__name__]):
  sys.modules[__name__] = require
