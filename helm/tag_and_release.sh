#!/usr/bin/env bash
#
# Copyright (c) 2021 , IRIS-HEP
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#
if [ "$#" -ne 2 ]; then
    echo "Usage: tag_release.sh serviceX_version chart_version"
fi

git checkout develop
git pull --ff-only origin develop

git checkout -b v$1

# Update the app version and chart version in the chart
sed -e "s/appVersion: .*$/appVersion: $1/" -e "s/version: .*$/version: $2/" servicex/Chart.yaml > servicex/Chart.new.yaml
mv servicex/Chart.new.yaml servicex/Chart.yaml
git add servicex/Chart.yaml

# Point all images in values.yaml to the new deployment
sed -e "s/  tag: develop/  tag: v$1/" -e "s/:develop/:v$1/" servicex/values.yaml > servicex/values.new.yaml
mv servicex/values.new.yaml servicex/values.yaml
git add servicex/values.yaml

git commit -m "Deploy version $1"
git push origin v$1

pushd ../Servicex_App || exit 0
./tag_and_release.sh $1
popd || exit 0

pushd ../X509_Secrets || exit 0
./tag_and_release.sh $1
popd || exit 0

pushd ../ServiceX_DID_Finder_Rucio || exit 0
./tag_and_release.sh $1
popd || exit 0

pushd ../ServiceX_DID_Finder_CERNOpenData || exit 0
./tag_and_release.sh $1
popd || exit 0

pushd ../ServiceX_xAOD_CPP_transformer || exit 0
echo "-- Skipping release of ../ServiceX_xAOD_CPP_transformer"
popd || exit 0

pushd ../ServiceX_Uproot_Transformer || exit 0
./tag_and_release.sh $1
popd || exit 0

pushd ../ServiceX_Code_Generator_FuncADL_xAOD || exit 0
./tag_and_release.sh $1
popd || exit 0

pushd ../ServiceX_Code_Generator_FuncADL_uproot || exit 0
./tag_and_release.sh $1
popd || exit 0

# Publish the chart
helm package servicex
mv servicex-$2.tgz ../ssl-helm-charts

pushd .. || exit 0
helm repo index ssl-helm-charts --url https://ssl-hep.github.io/ssl-helm-charts/

cd ssl-helm-charts
git add index.yaml
git add servicex-$2
git commit -m "Release $1"
git push origin gh-pages
pop || exit 0
echo "Version $1 has been released!"
