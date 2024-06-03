# Copyright (c) 2019, IRIS-HEP
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
import os
import shutil

from servicex_codegen.code_generator import CodeGenerator, GeneratedFileResult, \
    GenerateCodeException


class RawUprootTranslator(CodeGenerator):
    # Generate the code. Ignoring caching for now
    def generate_code(self, query, cache_path: str):
        import hashlib

        if len(query) == 0:
            raise GenerateCodeException("Requested codegen for an empty string.")

        import json
        jquery = json.loads(query)

        if not isinstance(jquery, list):
            raise GenerateCodeException("Provided query is not a list")

        for subquery in jquery:
            if (('treename' not in subquery or not subquery['treename'])
                    and ('copy_histograms' not in subquery or not subquery['copy_histograms'])):
                raise GenerateCodeException("At least one tree or histogram must be "
                                            f"specified for query {subquery}")

        generated_code = f'''
def run_query(file_path):
    jquery = {jquery}

    rv_arrays_trees = {{}}; rv_arrays_histograms = {{}}
    for subquery in jquery:
        a, b = run_single_query(file_path, subquery)
        rv_arrays_trees.update(a); rv_arrays_histograms.update(b)
    return rv_arrays_trees, rv_arrays_histograms

def run_single_query(file_path, query):
    import uproot
    import awkward as ak

    lang = uproot.language.python.PythonLanguage()
    lang.functions.update({{ 'concatenate': ak.concatenate,
                             'where': ak.where,
                             'flatten': ak.flatten,
                             'num': ak.num,
                             'count': ak.count,
                             'count_nonzero': ak.count_nonzero,
                             'sum': ak.sum,
                             'nansum': ak.nansum,
                             'prod': ak.prod,
                             'nanprod': ak.nanprod,
                             'any': ak.any,
                             'all': ak.all,
                             'min': ak.min,
                             'nanmin': ak.nanmin,
                             'max': ak.max,
                             'nanmax': ak.nanmax,
                             'argmin': ak.argmin,
                             'nanargmin': ak.nanargmin,
                             'argmax': ak.argmax,
                             'nanargmax': ak.nanargmax,
                             'moment': ak.moment,
                             'mean': ak.mean,
                             'nanmean': ak.nanmean,
                             'var': ak.var,
                             'nanvar': ak.nanvar,
                             'std': ak.std,
                             'nanstd': ak.nanstd,
                             'softmax': ak.softmax,
                             'sort': ak.sort,
                             'argsort': ak.argsort,
                             'mask': ak.mask,
                             'is_none': ak.is_none,
                             'drop_none': ak.drop_none,
                             'pad_none': ak.pad_none,
                             'fill_none': ak.fill_none,
                             'firsts': ak.firsts,
                             'singletons': ak.singletons,
                             'broadcast_arrays': ak.broadcast_arrays,
                             'broadcast_fields': ak.broadcast_fields,
                             'cartesian': ak.cartesian,
                             'argcartesian': ak.argcartesian,
                             'combinations': ak.combinations,
                             'argcombinations': ak.argcombinations,
                             'isclose': ak.isclose,
                             'almost_equal': ak.almost_equal,
                           }})

    sanitized_args = {{'expressions': query.get('expressions'),
                       'cut': query.get('cut'),
                       'filter_name': query.get('filter_name'),
                       'aliases': query.get('aliases')}}

    rv_arrays_trees = {{}}; rv_arrays_histograms = {{}}
    with uproot.open({{file_path: None}}) as fl:
        if 'treename' in query:
            trees = query['treename']
            if isinstance(trees, str):
                trees = [trees]
            if isinstance(trees, list):
                trees = {{_:_ for _ in trees}}
            for treename, outtreename in trees.items():
                # exception will be propagated up if tree does not exist
                t = fl[treename]
                arr = None
                for subarr in t.iterate(language=lang, **sanitized_args):
                    if arr is None:
                        arr = subarr
                    else:
                        arr = ak.concatenate([arr, subarr])
                if len(arr):
                    rv_arrays_trees[outtreename] = (arr, None)
                else: # want to return empty tree, but need to extract metadata to do so
                    if 'cut' in sanitized_args:
                        sanitized_args.pop('cut')
                    arr = t.arrays(language=lang, entry_stop=1, **sanitized_args)
                    rv_arrays_trees[outtreename] = (None, {{_: arr[_].type for _ in arr.fields}})
        else:
            histograms = query['copy_histograms']
            keys = fl.keys(filter_name=histograms, cycle=False)
            for key in keys:
                rv_arrays_histograms[key] = fl[key]

    return rv_arrays_trees, rv_arrays_histograms
'''

        _hash = hashlib.md5(generated_code.encode(), usedforsecurity=False).hexdigest()
        query_file_path = os.path.join(cache_path, _hash)

        # Create the files to run in that location.
        if not os.path.exists(query_file_path):
            os.makedirs(query_file_path)

        with open(os.path.join(query_file_path, 'generated_transformer.py'), 'w') as python_file:
            python_file.write(generated_code)

        # Transfer the templated main python script
        template_path = os.environ.get('TEMPLATE_PATH',
                                       "/home/servicex/servicex/templates/transform_single_file.py")  # NOQA: 501
        shutil.copyfile(template_path, os.path.join(query_file_path, "transform_single_file.py"))

        capabilities_path = os.environ.get('CAPABILITIES_PATH',
                                           "/home/servicex/transformer_capabilities.json")
        shutil.copyfile(capabilities_path, os.path.join(query_file_path,
                                                        "transformer_capabilities.json"))

        return GeneratedFileResult(_hash, query_file_path)
