# require() for Python

This Python module provides a new approach to loading Python modules
similar to Node's `require()` that is  decoupled from the Python import
mechanism.

```python
import require
status = require('./lib/status')
status.yell()
```

This is particularly useful in Python applications with a plugin architecture
and solves potential problems when using traditional Python modules that can
easily result in dependency conflicts.

## Installation

    pip install py-require

## Known Issues

- In Python 2, no statement must be on the first line of the file. This is
  due to the fact that require prepends the text `from __future__ import absolute_import;`
  in the first first line to avoid RuntimeWarnings when import other modules
  using Pythons standard `import` mechanism.

## API

#### `require(file, directory=None, path=(), reload=False, cascade=False, inplace=False, get_exports=True)`

> Loads a Python module by filename. If *file* is a relative path starting
> with `./`, it will be loaded relative to *directory*. Otherwise, if it
> is not an absolute path, it will be searched in the search *path*. Note
> that *file* should be a UNIX-style path on every platform.
>
> The algorithm will check the following forms of *file*:
>
> - `<file>`
> - `<file>c@x-y`
> - `<file>/__init__.py`
> - `<file>/__init__.pyc@x-y`
> - `<file>.py`
> - `<file>.pyc@x-y`
>
> `c@x-y` is the suffix of bytecode files for the current Python version.
> If *file* is the string `'.'`, it will be translated to `'./__init__.py'`.
>
> __Parameters__
>
> - *file* -- The name of the Python module to load.  
> - *directory* -- The directory to load a local module from. If omitted,
>   will be determined automatically from the caller's global scope using
>   `sys._getframe()`.  
> - *path* -- A list of additional search paths when loading other
>   modules with `require()`. Subsequent loads inherit this search path.
> - *reload* -- True to force reload the module.  
> - *cascade* -- If *reload* is True, passing True causes a cascade
>   reload.  
> - *inplace* -- If *reload* is True, modules will be reloaded in-place
>   instead of creating a new module object.
> - *get_exports* -- Return the `exports` member of the module if there
>   is any. False can be passed to always get the actual module object. Can
>   also be callable that is passed the module object. The result of this
>   callable is returned.
>
> __Return__
>
> A `types.ModuleType` object, unless the module has a member called
> `exports`, in which case the value of this member will be returned.
>
> __Raises__
>
> `require.error` -- If the module could not be found or loaded.

#### `require.new()`

> Create a new `Require` object that is completely decoupled from the
> `require` module and has the exact same API.
>
> ```python
> import require
> require = require.new()
> require('./hello').say_hello()
> ```

#### `require.path`

> A list of global search directories that will always be taken into account
> when using `require()`.

#### `require.modules`

> This dictionary maps absolute filenames to the Python modules that are
> loaded by `require()`.



## Changelog

#### v0.11

- rewrite, using `Require` class and cleaner code base
- add `require.new()` (#11)
- support for translating `'.'` to `'./__init__.py'` (#10)
- fix bug with parent context not being inherited when calling the `require`
  module directly instead of using `require.require()`, by introducing a new
  *_stackdepth* parameter

#### v0.10

- fix #9 &ndash; `require` module is now a custom `types.ModuleType` instance
  that implements `__call__()`

#### v0.9

- add `require(get_exports)` parameter

#### v0.8

- removed `'.'` path from default value of `require.path`

#### v0.7

- rename module to `require` from `shroud`
- `sys.module` hook to allow calling `require` as a module instead of
  having to use `from require import require`
- directory to load local modules from (`./`) now falls back to the
  current working directory

## License

The MIT License (MIT)

Copyright (c) 2016  Niklas Rosenstein

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
