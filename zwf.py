"""
Tools for Zwift WAD files.
"""
from typing import Callable, Dict, Union
import sys
import traceback
import warnings
import os
import io
import struct
import fnmatch
from pathlib import Path

import docopt
from hurry.filesize import size as human_readable_size

__version__ = '0.0.0'

WAD_MAGIC = b'ZWF!'

docopt_usage = __doc__ + """
usage: 
    zwf list [options] <file>
    zwf extract [options] <file> <dir> [<glob>]

options:
    -l           List more information
    -H           Show file sizes in human-readable form
    --verbose    Print more info
    --traceback  Print stack trace on errors
"""


class CommandError(RuntimeError):
    pass


def read_wad(f: io.RawIOBase):
    f.seek(0)
    header = f.read(256)

    if header[:4] != WAD_MAGIC:
        raise CommandError(
            f'File does not appear to be a Zwift WAD file, Expected '
            f'magic: {WAD_MAGIC}, actual: {header[:4]}')

    body_size = struct.unpack('<I', header[248:252])[0]
    wad_size = 256 + body_size
    actual_size = os.fstat(f.fileno()).st_size

    if actual_size < wad_size:
        raise CommandError(f'Truncated wad file: header implies '
                           f'{wad_size} bytes but file is {actual_size} bytes')
    if actual_size > wad_size:
        warnings.warn(
            f'wad file is larger than header implies. expected size: '
            f'{actual_size} bytes, actual size: {actual_size} bytes')

    entry_pointers = read_entry_pointers(f)

    return {'file': f, 'entry_pointers': entry_pointers}


def read_entry_pointers(f):
    # There's a 8k block containing 8-byte chunks. First 4 bytes are a pointer
    # to a wad file entry, second 4 bytes seem to be either 0 or 1. When 0 the
    # pointer is null and the entry seems not to be used. Null and active
    # entries are spread throughout.
    data = f.read(1024*8)
    entries = list(struct.iter_unpack('<I?xxx', data))

    offset = min(ptr for ptr, in_use in entries if in_use) - 1024*8 - 256
    assert offset != 0

    return [ptr - offset for ptr, in_use in entries if in_use]


def cstring(data):
    end = data.index(b'\x00')
    if end < 0:
        return data
    return data[:end]


def read_wad_entry(wad, ptr,
                   include_body: Union[bool, Callable[[Dict], bool]] = True):
    f = wad['file']
    assert ptr in wad['entry_pointers']

    f.seek(ptr)
    header = f.read(192)

    # Not sure what encoding (if any) is used
    path = cstring(header[4:100]).decode('ascii')

    size = struct.unpack('<I', header[104:108])[0]

    entry = {
        'path': path,
        'size': size
    }

    if callable(include_body) and include_body(entry) or include_body:
        entry['body'] = f.read(size)

    return entry


def list_wad(wad, long_listing=False, human_readable_sizes=False):
    for ptr in wad['entry_pointers']:
        entry = read_wad_entry(wad, ptr, include_body=False)

        if long_listing:
            if human_readable_sizes:
                size = human_readable_size(entry['size'])
            else:
                size = entry['size']

            print(f'{size} {entry["path"]}')
        else:
            print(entry["path"])


def extract_wad(wad, dest_dir: Path, entry_predicate: Callable[[Dict], bool],
                verbose=False):
    if not dest_dir.is_dir():
        raise CommandError(
            f'Destination directory is not an existing directory')
    if next(dest_dir.iterdir(), None) is not None:
        raise CommandError(f'Destination dir is not empty')

    for ptr in wad['entry_pointers']:
        entry = read_wad_entry(wad, ptr, include_body=entry_predicate)

        if 'body' not in entry:
            continue

        entry_path = dest_dir / entry['path']
        if dest_dir not in entry_path.parents:
            raise CommandError(f'Entry would extract out of destination '
                               f'directory: {entry["path"]!r}')

        if verbose:
            print(f'  extracting: {entry["path"]} ... ', end='', flush=True)
        entry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(entry_path, 'wb') as f:
            f.write(entry['body'])
        if verbose:
            print(f'done')


def main():
    args = docopt.docopt(docopt_usage)
    try:
        f = open(args['<file>'], 'rb')

        wad = read_wad(f)

        if args['list']:
            list_wad(wad, long_listing=args['-l'],
                     human_readable_sizes=args['-H'])
        elif args['extract']:
            dest = Path(args['<dir>'])
            if args['--verbose']:
                print(f'  Zwift WAD:  {args["<file>"]}')
                print(f'Destination:  {dest}')

            predicate = lambda x: True
            if args['<glob>']:
                glob = args['<glob>']
                predicate = lambda entry: fnmatch.fnmatchcase(entry['path'],
                                                              glob)

            extract_wad(wad, dest, entry_predicate=predicate,
                        verbose=args['--verbose'])
        else:
            raise NotImplementedError()
    except CommandError as e:
        print(f'Fatal: {e}', file=sys.stderr)

        if args['--traceback']:
            print('\nTraceback follows:\n', file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)


if __name__ == '__main__':
    main()
