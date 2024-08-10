
def run_query(file_path):
    jquery = [{'treename': 'reco', 'expressions': None, 'cut': None, 'filter_name': 'el_pt_NOSYS', 'filter_typename': None, 'aliases': None}]

    rv_arrays_trees = {}; rv_arrays_histograms = {}
    for subquery in jquery:
        a, b = run_single_query(file_path, subquery)
        rv_arrays_trees.update(a); rv_arrays_histograms.update(b)
    return rv_arrays_trees, rv_arrays_histograms

def run_single_query(file_path, query):
    import uproot
    import awkward as ak

    lang = uproot.language.python.PythonLanguage()
    lang.functions.update({ 'concatenate': ak.concatenate,
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
                           })

    sanitized_args = {'expressions': query.get('expressions'),
                       'cut': query.get('cut'),
                       'filter_name': query.get('filter_name'),
                       'aliases': query.get('aliases')}

    rv_arrays_trees = {}; rv_arrays_histograms = {}
    with uproot.open({file_path: None}) as fl:
        if 'treename' in query:
            trees = query['treename']
            if isinstance(trees, str):
                trees = [trees]
            if isinstance(trees, list):
                trees = {_:_ for _ in trees}
            for treename, outtreename in trees.items():
                # exception will be propagated up if tree does not exist
                t = fl[treename]
                arr = None
                for subarr in t.iterate(language=lang, **sanitized_args):
                    if arr is None:
                        arr = subarr
                    else:
                        arr = ak.concatenate([arr, subarr])
                if arr is not None and len(arr):  # iterate will not give anything if tree empty
                    rv_arrays_trees[outtreename] = (arr, None)
                else:  # recent uproot handles zero-length case properly for arrays()
                    if 'cut' in sanitized_args:
                        sanitized_args.pop('cut')
                    arr = t.arrays(language=lang, entry_stop=0, **sanitized_args)
                    rv_arrays_trees[outtreename] = (None, {_: arr[_].type for _ in arr.fields})
        else:
            histograms = query['copy_histograms']
            keys = fl.keys(filter_name=histograms, cycle=False)
            for key in keys:
                rv_arrays_histograms[key] = fl[key]

    return rv_arrays_trees, rv_arrays_histograms
