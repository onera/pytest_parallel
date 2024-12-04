# ------------------------------------------------------------------------------
# General CMake settings
# ------------------------------------------------------------------------------
cmake_minimum_required(VERSION 3.14 FATAL_ERROR)
cmake_policy(SET CMP0074 NEW) # force find_package to take <PackageName>_ROOT variables into account


# ----------------------------------------------------------------------
# Project
# ----------------------------------------------------------------------
project(
  pytest_parallel VERSION 1.2.0
  DESCRIPTION "pytest_parallel extends PyTest to support parallel testing using mpi4py"
)


# ----------------------------------------------------------------------
# Find Python
# ----------------------------------------------------------------------
if (NOT DEFINED "Python_VERSION_MAJOR" OR
    NOT DEFINED "Python_VERSION_MINOR")
  find_package(Python 3.8 REQUIRED COMPONENTS Development.Module)
endif ()


# ----------------------------------------------------------------------
# Setup Python installation path
# ----------------------------------------------------------------------
if (Python_VERSION_MAJOR AND Python_VERSION_MINOR)
    set(_python_version_suffix "${Python_VERSION_MAJOR}.${Python_VERSION_MINOR}")
else ()
    message(WARNING "The version of Python is unknown; not using a versioned directory for Python modules.")
    set(_python_version_suffix)
endif ()
set(SITE_PACKAGES_OUTPUT_DIRECTORY "${CMAKE_INSTALL_PREFIX}/lib/python${_python_version_suffix}/site-packages/")


# ----------------------------------------------------------------------
# Find and install Python files
# ----------------------------------------------------------------------
file(GLOB_RECURSE py_files CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/pytest_parallel/*.py")

foreach (py_file ${py_files})
  file(RELATIVE_PATH py_file_rel  ${CMAKE_CURRENT_SOURCE_DIR} ${py_file})

  get_filename_component(py_dir_rel "${py_file_rel}" DIRECTORY)
  install(FILES       "${py_file_rel}"
          DESTINATION "${SITE_PACKAGES_OUTPUT_DIRECTORY}/${py_dir_rel}"
          COMPONENT   "Python files")
endforeach ()
