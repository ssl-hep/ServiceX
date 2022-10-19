#!/usr/bin/env bash
git checkout develop
git pull origin develop

helm dependencies update servicex

# Update the app version and chart version in the chart
sed -e "s/appVersion: .*$/appVersion: $1/" -e "s/version: .*$/version: $1/" servicex/Chart.yaml > servicex/Chart.new.yaml
mv servicex/Chart.new.yaml servicex/Chart.yaml

# Point all images in values.yaml to the new deployment
sed -E -e "s/  tag:\s*[[:digit:]]{8}-[[:digit:]]{4}-stable.*$/  tag: $1/" -e "s/  defaultTransformerTag:\s*.+$/  defaultTransformerTag: $1/" servicex/values.yaml > servicex/values.new.yaml
mv servicex/values.new.yaml servicex/values.yaml
helm package servicex




