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
__version__ = '0.10'

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

class Require(types.ModuleType):

  error = RequireError

  def __init__(self, path=(), _keep_alive=None):
    super(Require, self).__init__('require')
    self.bytecache_suffix = 'c@' + sys.version[:3].replace('.', '-')
    self.modules = {}
    self.path = list(path)
    self.cascade_index = 0
    self._keep_alive = _keep_alive
    if _keep_alive:
      self.__file__ = _keep_alive.__file__

  @staticmethod
  def new(path=()):
    return Require(path)

  def require(self, file, directory=None, path=(), reload=False,
              cascade=False, inplace=False, get_exports=True):
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

    parent_globals = sys._getframe(1).f_globals
    parent_context = parent_globals.get('__require_module_context')
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

    load_file = self._get_best_candidate(file, directory, path, parent_context)
    if not load_file:
      raise self.error(file)

    # The best candidate can be a bytecode version, thus we eventually
    # need to remove that suffix again to get the source .py file.
    if load_file.endswith(self.bytecache_suffix):
      mode = 'bytecode'
      file_ident = load_file[:-len(bcsuffix)]
    else:
      mode = 'source'
      file_ident = load_file

    mod = self.modules.get(file_ident)
    if not reload and mod is not None:
      return get_exports(mod)
    if reload and cascade and mod is not None:
      # If we're still in the same cascade, don't load the module again.
      if mod.__require_module_context.cascade_index == cascade_index:
        return get_exports(mod)

    context = RequireModuleContext(path, reload, cascade, inplace,
      cascade_index, parent_context)

    if not (mod is not None and reload and inplace):
      mod = types.ModuleType(file_ident)
    mod.__file__ = load_file
    mod.__require_module_context = context
    mod.require = self
    self.modules[file_ident] = mod

    try:
      code = self._exec_module(mod, load_file, mode)
    except BaseException:
      self.modules.pop(load_file, None)
      raise

    if not sys.dont_write_bytecode:
      try:
        self._write_bytecode(code, load_file + self.bytecache_suffix)
      except (OSError, IOError):
        pass # intentional

    return get_exports(mod)

  def __call__(self, *args, **kwargs):
    """ Alias for ``require()``. """
    return self.require(*args, **kwargs)

  def _get_best_candidate(self, file, main_dir, search_path, parent_context):
    path_chain = [main_dir, self.path, search_path]
    curr_context = parent_context
    while curr_context:
      path_chain.append(curr_context.path)
      curr_context = curr_context.parent

    for dirname in itertools.chain(*path_chain):
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
      elif os.path.isfile(curr + self.bytecache_suffix):
        return curr + self.bytecache_suffix  # use existing cache file
      elif os.path.isdir(curr):
        temp = os.path.join(curr, '__init__.py')
        if not os.path.isfile(temp):
          temp += self.bytecache_suffix  # check existing cache file
        if os.path.isfile(temp):
          return temp

      if quit:
        break  # We don't need to do this again if the file is absolute

    if not file.endswith('.py'):
      # Try again.
      return self._get_best_candidate(file + '.py', main_dir, search_path, parent_context)

    return None

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

if __name__ in sys.modules:
  sys.modules[__name__] = Require(_keep_alive=sys.modules[__name__])
