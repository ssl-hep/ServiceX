#!/bin/env bash

# If any problem occurs during the running of this script we want to bail and make sure that
# everyone above us knows what happened.
set -e

# Meant to be invokved in an ATLAS R21 analysis container.
# This follows the tutorial from https://atlassoftwaredocs.web.cern.ch/ABtutorial/release_setup/

# Parse the command line arguments. Our defaults
output_method="cp"
output_dir="/results"
input_method="filelist"
input_file=""
compile=1
run=1

while getopts "d:cr" opt; do
    case "$opt" in
    d)
        input_method="cmd"
        input_file=$OPTARG
        ;;
    c)
        run=0
        ;;
    r)
        compile=0
        ;;
    ?)
        exit 10
    esac
done

# If there are any arguments left over, then very bad things have happened.
shift $((OPTIND-1))
if [ $# != 0 ]; then
  echo "Extra arguments on the command line $@"
  exit 1
fi

# Setup and config
source /home/atlas/release_setup.sh

# Remember where we are and the script location.
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
local=`pwd`

# Create a release directory
if [ $compile = 1 ]; then
   mkdir rel
   cd rel
   mkdir source
   mkdir build
   mkdir run

# Create cmake infrastructure
   cat > source/CMakeLists.txt << 'EOF'
#
# Project configuration for UserAnalysis.
#

# Set the minimum required CMake version:
cmake_minimum_required( VERSION 3.4 FATAL_ERROR )

# Try to figure out what project is our parent. Just using a hard-coded list
# of possible project names. Basically the names of all the other
# sub-directories inside the Projects/ directory in the repository.
set( _parentProjectNames Athena AthenaP1 AnalysisBase AthAnalysis
   AthSimulation AthDerivation AnalysisTop )
set( _defaultParentProject AnalysisBase )
foreach( _pp ${_parentProjectNames} )
   if( NOT "$ENV{${_pp}_DIR}" STREQUAL "" )
      set( _defaultParentProject ${_pp} )
      break()
   endif()
endforeach()

# Set the parent project name based on the previous findings:
set( ATLAS_PROJECT ${_defaultParentProject}
   CACHE STRING "The name of the parent project to build against" )

# Clean up:
unset( _parentProjectNames )
unset( _defaultParentProject )

# Find the AnalysisBase project. This is what, amongst other things, pulls
# in the definition of all of the "atlas_" prefixed functions/macros.
find_package( ${ATLAS_PROJECT} REQUIRED )

# Set up CTest. This makes sure that per-package build log files can be
# created if the user so chooses.
atlas_ctest_setup()

# Set up the GitAnalysisTutorial project. With this CMake will look for "packages"
# in the current repository and all of its submodules, respecting the
# "package_filters.txt" file, and set up the build of those packages.
atlas_project( UserAnalysis 1.0.0
   USE ${ATLAS_PROJECT} ${${ATLAS_PROJECT}_VERSION} )

# Set up the runtime environment setup script. This makes sure that the
# project's "setup.sh" script can set up a fully functional runtime environment,
# including all the externals that the project uses.
lcg_generate_env( SH_FILE ${CMAKE_BINARY_DIR}/${ATLAS_PLATFORM}/env_setup.sh )
install( FILES ${CMAKE_BINARY_DIR}/${ATLAS_PLATFORM}/env_setup.sh
   DESTINATION . )

# Set up CPack. This call makes sure that an RPM or TGZ file can be created
# from the built project. Used by Panda to send the project to the grid worker
# nodes.
atlas_cpack_setup()
EOF

   # Create a package infrastructure
   cd source
   mkdir analysis
   mkdir analysis/analysis
   mkdir analysis/Root
   mkdir analysis/src
   mkdir analysis/src/components
   mkdir analysis/share

   # Create the basics for cmake
   cp $DIR/package_CMakeLists.txt analysis/CMakeLists.txt

   # Next, copy over the algorithm. The source directory needs to be correctly mounted.
   cp $DIR/query.h analysis/analysis
   cp $DIR/query.cxx analysis/Root
   cp $DIR/ATestRun_eljob.py analysis/share
   chmod +x analysis/share/ATestRun_eljob.py

   cat > analysis/analysis/queryDict.h << EOF
#ifndef analysis_query_DICT_H
#define analysis_query_DICT_H

// This file includes all the header files that you need to create
// dictionaries for.

#include <analysis/query.h>

#endif
EOF

   cat > analysis/analysis/selection.xml << EOF
<lcgdict>

  <!-- This file contains a list of all classes for which a dictionary
       should be created. -->

  <class name="query" />
   
</lcgdict>
EOF


   # Do the build
   cd ../build
   cmake ../source
   make
else
   cd rel/build
fi

# Sort out the input file location
if [ $run = 1 ]; then
   source ${AnalysisBaseExternals_PLATFORM}/setup.sh
   if [ "$input_method" == "filelist" ]; then
      if [ -e $DIR/filelist.txt ]; then
         cp $DIR/filelist.txt .
      else
         cp $local/filelist.txt .
      fi
   elif [ "$input_method" == "cmd" ]; then
      echo $input_file > filelist.txt
   fi

   # Do the run
   if [ -e ./bogus ]; then
     rm -rf bogus
   fi
   python ../source/analysis/share/ATestRun_eljob.py --submission-dir=bogus

   # Place the output file where it belongs
   if [ $output_method == "cp" ]; then
      cmd="cp"
      destination=$output_dir
   else
      destination=$1
      cmd="cp"
      if [[ $destination == "root:"* ]]; then
         cmd="xrdcp"
      fi
   fi
   $cmd ./bogus/data-ANALYSIS/ANALYSIS.root $destination
fi