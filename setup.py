"""Setup for pycapy"""
from setuptools import setup, Extension
from itertools import chain
from io import open
import glob
import os
import sys
import urllib.request
import zipfile
from Cython.Build import cythonize

PACKAGE = "pypcap"
VERSION = "1.2.2"

def recursive_search_dirs(dirs, target_files):
    """Recursive search directories"""
    for d in dirs:
        r = recursive_search(d, target_files)
        if r:
            return r


def recursive_search(path, target_files):
    """Recursively search for files"""
    for root, _dirs, files in os.walk(path):
        for filename in files:
            if filename in target_files:
                return os.path.join(root, filename)


def find_prefix_and_pcap_h():
    prefixes = chain.from_iterable((
        ('/usr', sys.prefix),
        glob.glob('/opt/libpcap*'),
        glob.glob('../libpcap*'),
        glob.glob('../wpdpack*'),
        glob.glob('/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/*'),
        glob.glob('/Library/Developer/CommandLineTools/SDKs/*'),
    ))

    # Find 'pcap.h'
    for prefix in prefixes:
        search_dirs = (
            os.path.join(prefix, 'local', 'include'),
            os.path.join(prefix, 'usr', 'include'),
            os.path.join(prefix, 'include'),
            prefix,
        )

        pcap_h = recursive_search_dirs(search_dirs, ['pcap.h'])
        if pcap_h:
            print("Found pcap headers in %s" % pcap_h)
            return (prefix, pcap_h)
    print("pcap.h not found")
    sys.exit(1)


def find_lib_path_and_file(prefix):
    if sys.maxsize > 2 ** 32:
        candidates = [
            'lib64',
            'lib/x64',  # wpdpack
            'lib/x86_64-linux-gnu'
            'lib',
            'lib/i386-linux-gnu',
            ''
        ]
    else:
        candidates = [
            'lib',
            'lib/i386-linux-gnu',
            ''
        ]
    lib_sub_dirs = [
        os.path.join(prefix, d) for d in candidates
    ]
    # For Mac OSX the default system pcap lib is in /usr/lib
    lib_sub_dirs.append('/usr/lib')

    lib_files = [
        'libpcap.a',
        'libpcap.so',
        'libpcap.dylib',
        'wpcap.lib'
    ]
    lib_file_path = recursive_search_dirs(lib_sub_dirs, lib_files)
    if not lib_file_path:
        print("None of the following found: %s" % lib_files)
        sys.exit(1)
        return
    print("Found libraries in %s" % lib_file_path)

    lib_path = os.path.dirname(lib_file_path)
    lib_file = os.path.basename(lib_file_path)
    return lib_path, lib_file


def find_define_macros(pcap_h):
    alternative = os.path.join(os.path.dirname(pcap_h), 'pcap', 'pcap.h')
    if os.path.exists(alternative):
        # Read pcap/pcap.h as well
        for macro in find_define_macros(alternative):
            yield macro
    with open(pcap_h, 'r',
              encoding='utf-8',
              errors='surrogateescape') as fi:
        for line in fi.readlines():
            if 'pcap_file(' in line:
                print("found pcap_file function")
                yield ('HAVE_PCAP_FILE', 1)
            elif 'pcap_compile_nopcap(' in line:
                print("found pcap_compile_nopcap function")
                yield ('HAVE_PCAP_COMPILE_NOPCAP', 1)
            elif 'pcap_setnonblock(' in line:
                print("found pcap_setnonblock")
                yield ('HAVE_PCAP_SETNONBLOCK', 1)
            elif 'pcap_setdirection(' in line:
                print("found pcap_setdirection")
                yield ('HAVE_PCAP_SETDIRECTION', 1)


def get_extension():
    prefix, pcap_h = find_prefix_and_pcap_h()
    lib_path, lib_file = find_lib_path_and_file(prefix)

    if lib_file == 'wpcap.lib':
        libraries = ['wpcap', 'iphlpapi']
        extra_compile_args = ['-DWIN32', '-DWPCAP', '-D_CRT_SECURE_NO_WARNINGS']
    else:
        libraries = ['pcap']
        extra_compile_args = []

    if os.name == 'nt':
        cythonize('winpcap.pyx')
        os.rename(os.path.dirname(os.path.abspath(__file__)) + '/winpcap.c', os.path.dirname(os.path.abspath(__file__)) + '/pcap.c')
    else:
        cythonize('pcap.pyx')

    return Extension(
        name='pcap',
        sources=['pcap.c', 'pcap_ex.c'],
        include_dirs=[os.path.dirname(pcap_h)],
        define_macros=list(find_define_macros(pcap_h)),
        library_dirs=[lib_path],
        libraries=libraries,
        extra_compile_args=extra_compile_args
    )


if __name__ == '__main__':
    os.remove(os.path.dirname(os.path.abspath(__file__)) + '/../npcap.zip')
    os.remove(os.path.dirname(os.path.abspath(__file__)) + '/pcap.c')

    print('Downloading Npcap SDK...')
    url = 'https://nmap.org/npcap/dist/npcap-sdk-1.01.zip'
    response = urllib.request.urlopen(url)
    data = response.read()
    zip = open(os.path.dirname(os.path.abspath(__file__)) + '/../npcap.zip', 'wb')
    zip.write(data)
    zip.close()
    print('Uncompressing Npcap SDK...')
    with zipfile.ZipFile(os.path.dirname(os.path.abspath(__file__)) + '/npcap.zip', 'r') as zip_ref:
        zip_ref.extractall(os.path.dirname(os.path.abspath(__file__)) + '/../wpdpack/')

    setup(
        name=PACKAGE,
        version=VERSION,
        author='Dug Song',
        author_email='dugsong@monkey.org',
        url='https://github.com/pynetwork/pypcap',
        description='pypcap -- Python interface to pcap a packet capture library',
        tests_require=['dpkt'],
        ext_modules=[get_extension()],
    )
