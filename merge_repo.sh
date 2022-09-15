#!/bin/bash
#
# Copyright (c) 2022 , IRIS-HEP
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

set -euo pipefail

show-stage() {
  echo -e $'\e[1;33m'"\n\n= $1 =\n"$'\e[0m'
}

GIT_REMOTE_WEB="git@github.com:funcx-faas/funcx-web-service.git"
GIT_REMOTE_WS="git@github.com:funcx-faas/funcx-websocket-service.git"
GIT_REMOTE_FORWARDER="git@github.com:funcx-faas/funcx-forwarder.git"
GIT_REMOTE_HELM="git@github.com:funcx-faas/helm-chart.git"

# handle args
while [ $# -gt 0 ]; do
  case "$1" in
    "-h" | "--help")
      echo "repo-merge.sh [-h|--help] [--delete]"
      exit 0
      ;;
    "--delete")
      rm -rf "./repo-merge/"
      ;;
    *)
      echo $'\e[31m'"argument '$1' not recognized"$'\e[0m' >&2
      exit 2
      ;;
  esac
  shift 1
done


if [ -d ./repo-merge ]; then
  echo 'repo-merge exists! abort!'
  exit 2
fi

add-remote () {
  git remote add --fetch "$1" "$2"
}

add-remote web-service "$GIT_REMOTE_WEB"
add-remote websocket-service "$GIT_REMOTE_WS"
add-remote forwarder "$GIT_REMOTE_FORWARDER"
add-remote helm-chart "$GIT_REMOTE_HELM"

merge-repo-setup() {
  show-stage "begin merge of $1..."
  git branch "$1-monorepo" "$1/main"
  git checkout "$1-monorepo"
  mkdir "$1"
  git ls-tree -z --name-only HEAD | xargs -0 -i git mv {} "$1/"
  git commit -m "monorepo-merge: move into $1/"
  git checkout main
}

merge-repo () {
  merge-repo-setup "$1"
  git merge -s recursive -X no-renames --no-edit "$1-monorepo" --allow-unrelated-histories
  show-stage "...finished merge of $1"
}

merge-web-service-and-forwarder () {
  merge-repo web-service
  merge-repo-setup forwarder
  show-stage "beginning merge of repos with shared history"
  git merge forwarder-monorepo || true  # this merge will find conflicts

  show-stage "CONFLICTS EXPECTED. PLEASE REMAIN CALM."
  # keep the new `forwarder/` files
  git add forwarder
  # discard changes to `web-service/`
  git checkout HEAD -- web-service/
  # now, keep changes done in both -- removal of files
  git add .
  git commit -m "monorepo-merge: re-merge web-service and forwarder"
  show-stage "...finished web-service+forwarder merge"
}

show-stage "begin repo merges"
merge-web-service-and-forwarder
merge-repo helm-chart
merge-repo websocket-service


# generate files
show-stage "creating root files"
echo "# FuncX Services" > README.md
cat > .pre-commit-config.yaml <<EOH
repos:
- repo: meta
  hooks:
    - id: check-hooks-apply
    - id: check-useless-excludes
- repo: https://github.com/pre-commit/pre-commit-hooks.git
  rev: v4.0.1
  hooks:
    - id: check-merge-conflict
    - id: trailing-whitespace
- repo: https://github.com/sirosen/check-jsonschema
  rev: 0.10.1
  hooks:
    - id: check-github-workflows
- repo: https://github.com/pycqa/flake8
  rev: 3.9.2
  hooks:
    - id: flake8
      exclude: ^web-service/migrations/.*
      additional_dependencies: ['flake8-bugbear==21.4.3']
- repo: https://github.com/python/black
  rev: 21.9b0
  hooks:
    - id: black
- repo: https://github.com/timothycrosley/isort
  rev: 5.9.3
  hooks:
    - id: isort
- repo: https://github.com/asottile/pyupgrade
  rev: v2.29.0
  hooks:
    - id: pyupgrade
      args: ["--py36-plus"]
- repo: https://github.com/gruntwork-io/pre-commit
  rev: v0.1.15
  hooks:
    - id: helmlint
EOH
git add README.md .pre-commit-config.yaml
git commit -m "Base monorepo files"