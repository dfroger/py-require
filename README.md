# Shroud

Shroud allows you to load Python modules in a `require()` style.

```python
from shroud import require
status = require('lib/status')
status.yell()
```

This is particularly useful in Python applications with a plugin architecture
and solves potential problems when using traditional Python modules that can
easily result in dependency conflicts.

## Installation

    pip install shroud-require

## API

#### `shroud.modules`

A dictionary like `sys.modules` that caches the modules that have already
been loaded with `require()`. The keys in this dictionary are the absolute
paths to the Python source files of the modules.

#### `shroud.require(path, directory=None, reload=False, cascade=False, inplace=False)`

Loads a Python module by filename. Can fall back to bytecode cache file
if available and writes them if `sys.dont_write_bytecode` is not enabled.
For modules loaded with `require()`, the `__name__` global variable
will be the path to the Python source file (even for cache files and even
if the source file does not exist).

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
