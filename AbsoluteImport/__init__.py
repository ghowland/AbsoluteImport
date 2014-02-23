#Author: Geoff Howland
#Project: AbsoluteImport             http://code.google.com/p/absoluteimport/
#Licensed under the MIT License:     http://en.wikipedia.org/wiki/MIT_License
"""
AbsoluteImport

AbsoluteImport ensures module and package imports always work, from relative or absolute path.  
Cyclical imports are fine.
"""


# AbsoluteImport: 
# 
# - Get absolute path from the relative path give (or take absolute path)
# - Load module, store in absolute path key
# - Reload() module is available
# - Always returns latest version of module, will not change a module until a requesting module re-requests it, so running while reloading will not cause problems.
# - Should be all thats required
#
# Implement:  Import(), Reload()


import imp
import py_compile
import os
import sys
import logging
import stat
import traceback
import time


def log(text, level=None):
  """Quick drop in"""
  global LOGGING_LEVEL
  if LOGGING_LEVEL == logging.DEBUG:
    print(text)


# Change this module level setting to get output for what is going on
LOGGING_LEVEL = logging.DEBUG

# Keep track of when the Python files changed, because we have to remove the
#   .pyc files, or they will not compile.  Found through usage.
PYTHON_FILE_STAT_CACHE = {}

# Absolute path key 
PYTHON_FILE_MODULE = {}

# We can register paths to be used as path prefixes
REGISTERED_PATH_PREFIXES = {}

# Dictionary for which modules are currently being imported, to deal with threading issues
#TODO(g): This should really use a ThreadSafeDict.  They all should...
IMPORTING_MODULES = {}

IMPORTING_WAIT_DELAY = 0.001

STARTUP_PATH = None


class Module:
  """Module class replacement, so we can perform circular imports by setting all the values"""

  def __init__(self, path):
    self.__asb_import_module_path__ = path

  def __repr__(self):
    output = 'Module: %s' % self.__asb_import_module_path__
    return output

  def __getattr__(self, name):
    """Ensure that accessing members doesnt fail due to threading and Import race conditions"""
    while self.__asb_import_module_path__ in IMPORTING_MODULES:
      log('\n\nThreading conflict on files: %s (waiting %0.3f)\n\n' % (self.__asb_import_module_path__, IMPORTING_WAIT_DELAY))
      time.sleep(IMPORTING_WAIT_DELAY)

    try:
      # Log must be inside try, or it loops forever on missing values, displaying this same message.  No depth is passed, so the request cannot know it's recursing
      log('GET ATTRIBUTE: %s: %s' % (self.__asb_import_module_path__, name))

      result = getattr(self, name)
    except AttributeError as e:
      log('Cannot find attribute in module: %s: %s' % (name, self.__asb_import_module_path__))
      # Timeout for retrying
      TIMEOUT = 2.0
      DELAY = 0.001
      started = time.time()
      found = False
      while started + TIMEOUT > time.time() and not found:
        try:
          result = getattr(self, name)
          found = True
        except AttributeError as e:
          log('Still cannot find attribute in module: %s: %s' % (name, self.__asb_import_module_path__))
          time.sleep(DELAY)

      if not found:
        raise AttributeError('Could not find attribute after %0.1f secons in module: %s: %s' % (TIMEOUT, name, self.__asb_import_module_path__))

    return result
        




class ImportException(Exception):
  """Failed to import."""


def RegisterPathPrefix(name, path, force=False):
  """Stores a name and path to use for named reference passing.  

  This way all paths are imported with the same relative paths.

  Args:
    name: string, the name of the registered path prefix
    path: string, the path to prefix imports with, Absolute Paths are highly recommended here
    force: boolean, default false, if true this will updated an existing path, generally this is
        not desired, so that modules may make assumptions, but be overidden by previously imported
        modules.
  """
  global STARTUP_PATH
  global REGISTERED_PATH_PREFIXES

  # Ensure we always initialize the startup path
  if STARTUP_PATH == None:
    Init()

  # Only register the prefix if we are forcing it, or it doesnt already exist
  if force or name not in REGISTERED_PATH_PREFIXES:
    REGISTERED_PATH_PREFIXES[name] = os.path.abspath(path)

    #log('Register Path Prefix: %s: %s' % (name, REGISTERED_PATH_PREFIXES[name]))


def GetRegisteredPathPrefix(name):
  """Get our registered path.  Can be used to access data or whatever."""
  global REGISTERED_PATH_PREFIXES
  
  path = REGISTERED_PATH_PREFIXES.get(name, None)

  return path


def Init(path=None):
  """Initializate the relative path for performing imports.  If none is specified, the CWD is used."""
  global STARTUP_PATH
  if path == None:
    STARTUP_PATH = os.getcwd()
  else:
    STARTUP_PATH = os.path.abspath(relative_path)


def Import(script_filename, prefix=None, reload=True):
  """Will return a Python module for this script_filename, or raise an ImportException.

  Args:
    script_filename: string, absolute or relative path of Python module to import
    prefix: string, name used with RegisterPathPrefix to store path prefixes for 
        location indepdent relative paths
  """
  global PYTHON_FILE_STAT_CACHE
  global STARTUP_PATH
  global PYTHON_FILE_MODULE
  global REGISTERED_PATH_PREFIXES

  # Ensure if a prefix is specified, we have it
  if prefix != None and prefix not in REGISTERED_PATH_PREFIXES:
    raise ImportException('Named path prefix "%s" was never registered' % prefix)

  # Ensure we always initialize the startup path
  if STARTUP_PATH == None:
    Init()
  
  # Get the script file name for this item
  #log('Script: %s' % (script_filename))
  

  # If we were given a prefix, use it
  if prefix != None:
    script_filename = '%s/%s' % (REGISTERED_PATH_PREFIXES[prefix], script_filename)

  # Perform the path maniplation
  #TODO(g): Wrap this in a function, and generally clean all this junk up.  Experimentation is over now.  Time to go clean!
  stack = traceback.extract_stack()
  calling_file = stack[-2][0]
  calling_base_path = os.path.dirname(calling_file)

  # Get the name and path, we need them seperate
  script_name = os.path.basename(script_filename)
  path = os.path.dirname(script_filename)

  #print('Path: %s  Script: %s' % (path, script_name))

  if path.startswith('/'):
    name = '%s/%s' % (path, script_name)
  else:
    if calling_base_path:
      if calling_base_path.startswith('/'):
        name = '%s/%s/%s' % (calling_base_path, path, script_name)
      else:
        name = '%s/%s/%s/%s' % (STARTUP_PATH, calling_base_path, path, script_name)
    else:
      name = '%s/%s/%s' % (STARTUP_PATH, path, script_name)
 
  # Split the suffix off the name
  if name.endswith('.py'):
    name = name.split('.py', 1)[0]

  # print('Calling Path: %s' % calling_base_path)
  script_filename = '%s.py' % name
  script_path = os.path.dirname(script_filename)
  script_modulename = name
  absolute_script_module_path = os.path.abspath(script_modulename)
  #print('Import: %s' % script_filename)

  #   name = name[:-3]
  # else:
  #   # Skip this one, but report it as a critical failure
  #   log('Script is not a python text file or is improperly named: %s' % \
  #       script_filename, logging.CRITICAL)
  #   return None

  
  # imp.load_module needs this suffix description information that
  #   imp.getsuffixes() would return, but the documentation was weird, so
  #   Im just forcing it to be this which is the only thing I want to be
  #   valid anyway.  Fail if it's not.
  suffix_description = ('.py', 'r', imp.PY_SOURCE)
  
  # Set to True if we want to delete the existing compiled python bytecode
  script_stat = os.stat(script_filename)[stat.ST_MTIME]
  #log('Loading module: %s: %s -> %s' % (script_filename, PYTHON_FILE_STAT_CACHE.get(script_filename, None), script_stat))
  if reload and script_filename in PYTHON_FILE_STAT_CACHE:
    if PYTHON_FILE_STAT_CACHE[script_filename] < script_stat:
      #log('Clearing cached file, modified time: %s' % script_filename)

      # If this file exists, delete it
      if os.path.isfile('%sc' % script_filename):
        os.unlink('%sc' % script_filename)
      
      # Update the script time
      PYTHON_FILE_STAT_CACHE[script_filename] = script_stat

      # Remove the cached module
      del PYTHON_FILE_MODULE[absolute_script_module_path]


  #TODO(g): Use a lock and make thread-safe
  if absolute_script_module_path in PYTHON_FILE_MODULE:
    return PYTHON_FILE_MODULE[absolute_script_module_path]

  else:
    # Mark this module as being imported, so we can hold off on allowing member requests until its done
    IMPORTING_MODULES[absolute_script_module_path] = time.time()
    # Create a module to load members into
    PYTHON_FILE_MODULE[absolute_script_module_path] = Module(absolute_script_module_path)

  
  
  # Set the file pointer here, just so we dont error trying to close if unopened
  fp = None
  
  try:
    try:
      # Import this script, it should be a python script
      #TODO(g): Use py_compile.compile(file, cfile, dfile, doraise) to properly
      #   name modules, so there is no namespace collisions:
      #   http://docs.python.org/library/py_compile.html
      #script_module = imp.load_module(name, fp, path, suffix_description)
      # Compile this script module
      compiled_filename = '%sc' % script_filename
      path = os.path.dirname(compiled_filename)
      module_name = os.path.basename(compiled_filename)
      #TODO(g): When to use doraise?  Only during development?  Seems like its always better...
      py_compile.compile(script_filename, compiled_filename, doraise=True)
      #print('Compiled')
      #py_compile.compile(script_filename, compiled_filename)
      fp = open(compiled_filename, 'rb')
      suffix_description = ('.pyc', 'rb', imp.PY_COMPILED)
      #print('Prepped: %s: %s' % (module_name, script_path))
      script_module = imp.load_module(module_name, fp, script_path, suffix_description)
      #print('Loaded')
      
      # Save this in our shared state.  Use this instead of the cache?
      #sharedstate.Set('__internals.python', script_filename, script_module)
      pass#RE-IMPLEMENT

      # Store the script module into the absolute path name

      # Set all the script_module attributes into the Module class
      for attribute in dir(script_module):
        value = getattr(script_module, attribute)
        setattr(PYTHON_FILE_MODULE[absolute_script_module_path], attribute, value)
      
      # Get the modified time, and save in cache, so we know when to skip and when to reload
      PYTHON_FILE_STAT_CACHE[script_filename] = script_stat

      # We're done importing this module, so remove it from import
      del IMPORTING_MODULES[absolute_script_module_path]

      # Return the module
      return PYTHON_FILE_MODULE[absolute_script_module_path]
    
    except ImportError as e:
      log('Failed to import script: %s: %s' % \
          (os.path.abspath(script_filename), e), logging.CRITICAL)
    except Exception as e:
      # log('Failed to import script for non-import reasons: %s: %s (%s)' % \
      #     (script_filename, e, stack.Mini(5, 1)), logging.CRITICAL)
      log('Failed to import script for non-import reasons: %s: %s (%s)' % \
          (script_filename, e, 'FIX:No stack'), logging.CRITICAL)
  
  finally:
    # Close the file handle whether there was an exception or not
    if fp:
      fp.close()
    
  
  # Failed
  return None

