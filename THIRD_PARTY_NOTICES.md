# References and licenses

The integration follows the public model, picking, drag/resize, export and SSOT
contracts in shim9610/figgy (reference HEAD 84aa2783caa97d679c72b5c079fb4aea8bf1040e)
and the separation of accepted model state from UI drafts in shim9610/figgy-web
(reference HEAD b15290af0f5ca83c94bf60b066f9565b7e0d878c). Their renderer code and
Studio application are not copied into this package.

figgy-renderer and its bundled fonts retain their MIT/Apache-2.0 and OFL notices.
The font notices are shipped in `figgy/licenses/LICENSE-LiberationSans.txt` and
`figgy/licenses/LICENSE-ComicNeue.txt`, including when fonts are embedded in the
native extension.
The desktop extra uses PySide6/Qt; retain the licenses supplied by those packages.
The notebook extra uses anywidget and ipywidgets under their respective licenses.

## Packaged browser kernel

Generated JS/WASM assets use upstream `figgy` web package 0.13.1 and
`figgy-renderer` 0.16.1 at commit
`84aa2783caa97d679c72b5c079fb4aea8bf1040e`, under MIT OR Apache-2.0.
Rebuild path and asset hashes are documented in `docs/HOSTS.md` and
`python/figgy/assets/provenance.json`. The same bundled font licenses apply.

## Desktop UI fonts

The native egui UI embeds `epaint_default_fonts 0.36.2`'s Hack Regular,
Ubuntu Light, Noto Emoji Regular and emoji-icon-font. Their complete font
license texts are included as `python/figgy/licenses/LICENSE-Egui-*.txt`
(Hack/Bitstream terms, Ubuntu Font Licence, SIL OFL and icon-font MIT).
