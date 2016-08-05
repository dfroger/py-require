# Shroud

Shroud allows you to load Python modules in a `require()` style.

```python
from shroud import require
status = require('./lib/status')
status.yell()
```

This is particularly useful in Python applications with a plugin architecture
and solves potential problems when using traditional Python modules that can
easily result in dependency conflicts.

## Installation

    pip install shroud-require

## Known Issues

- In Python 2, no statement must be on the first line of the file. This is
  due to the fact that shroud prepends the text `from __future__ import absolute_import;`
  in the first first line to avoid RuntimeWarnings when import other modules
  using Pythons standard `import` mechanism.

## API

#### `shroud.modules`

> This dictionary maps absolute filenames to the Python modules that are
> loaded by `require()`.

#### `shroud.path`

> A list of global search directories that will always be taken into account
> when using `require()`.

#### `shroud.require(file, directory=None, path=(), reload=False, cascade=False, inplace=False)`

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
>
> __Parameters__
>
> *file* &ndash; The name of the Python module to load.  
> *directory* &ndash; The directory to load a local module from. If omitted,
>   will be determined automatically from the caller's global scope using
>   `sys._getframe()`.  
> *path* &ndash; A list of additional search paths to search for relative
>   modules. This path is considered before `shroud.path`.  
> *reload* &ndash; True to force reload the module.  
> *cascade* &ndash; If *reload* is True, passing True causes a cascade
>   reload.  
> *inplace* &ndash; If *reload* is True, modules will be reloaded in-place
>   instead of creating a new module object.
>
> __Return__
>
> A :class:`types.ModuleType` object, unless the module has a member called
> `exports`, in which case the value of this member will be returned.
>
> __Raises__
>
> *RequireError* &ndash; If the module could not be found or loaded.

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
