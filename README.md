# zwf — Zwift WAD file tool

A tool to list/extract files from Zwift WAD files — the asset archives (like a tar/zip file) that Zwift uses.

## Limitations

**Compressed .wad files are not supported**. The .wad files which ship with Zwift under `assets/**/*.wad` are compressed. This tool can work with the decompressed versions, but does not implement decompression itself. 

You might find decompressed versions in a memory dump of a Zwift process, but that may be against the Zwift TOS.
