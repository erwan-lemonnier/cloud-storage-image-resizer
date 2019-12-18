from setuptools import setup
import sys
import os

version = None

if sys.argv[-2] == '--version' and 'sdist' in sys.argv:
    version = sys.argv[-1]
    sys.argv.pop()
    sys.argv.pop()

if 'sdist' in sys.argv and not version:
    raise Exception("Please set a version with --version x.y.z")

if not version:
    if 'sdist' in sys.argv:
        raise Exception("Please set a version with --version x.y.z")
    else:
        path_pkg_info = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'PKG-INFO')
        if os.path.isfile(path_pkg_info):
            with open(path_pkg_info, 'r', encoding='utf-8') as f:
                for l in f.readlines():
                    if 'Version:' in l:
                        _, version = l.split(' ')
                        version = version.strip()
                        break
        else:
            print("WARNING: cannot set version in custom setup.py")

print("version: %s" % version)

# read the contents of the README file
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

desc = 'Import, rotate, crop and resize pictures into google Cloud Storage'
setup(
    name='google-cloud-storage-image-resizer',
    version=version,
    url='https://github.com/erwan-lemonnier/cloud-storage-image-resizer',
    license='BSD',
    author='Erwan Lemonnier',
    author_email='erwan@lemonnier.se',
    description=desc,
    long_description=long_description,
    long_description_content_type='text/markdown',
    install_requires=[
        'Pillow',
        'requests',
        'google-cloud-storage',
    ],
    tests_require=[
    ],
    test_suite='nose.collector',
    py_modules=['cloudstorageimageresizer'],
    platforms='any',
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
