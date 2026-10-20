# Third-party sources

- **BrickBuilderMCP** — [jonx/BrickBuilderMCP](https://github.com/jonx/BrickBuilderMCP), MIT, pinned commit `f397a80993e6e2d36aed50b96d2b6f7200fc1694`. Installed dependency supplies the original model state, common building helpers and connection graph. No installed source files are edited.
- **BrickNet** — [kulits/BrickNet](https://github.com/kulits/BrickNet), version 0.1.1, MIT, copyright (c) 2026 Peter Kulits. Installed dependency supplies convex collision queries and external collider assets. `catalog.json` contains a transformed 60-part subset of its connection labels, names and alias transforms. MIT notice reproduced below.
- **LDraw.org Parts Library** — [official library](https://library.ldraw.org/), created by the LDraw.org contributors credited in the individual part headers. External geometry retains its own CC BY 2.0 / CC BY 4.0 notices; see the downloaded `ldraw/CAreadme.txt`, `CAlicense.txt`, `CALicense4.txt` and individual `.dat` headers. `catalog.json` also contains derived bounds/origins. Geometry is downloaded into the ignored cache, not bundled into this repository. Generated previews use that geometry; attribution is provided here and in the project documentation. [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/).
- **BrickBench / BrickAgent / ldraw-mcp** — cited as design references in [docs/V2.md](docs/V2.md); no benchmark scores or external application compatibility are claimed.

## BrickNet MIT notice

MIT License

Copyright (c) 2026 Peter Kulits

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
