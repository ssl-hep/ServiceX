def run_query(input_filenames=None, tree_name=None):
    import functools, logging, numpy as np, dask_awkward as dak, uproot, vector
    vector.register_awkward()

    def _remove_not_interpretable(branch):
        if isinstance(branch.interpretation, uproot.interpretation.identify.uproot.AsGrouped):
            for name, interpretation in branch.interpretation.subbranches.items():
                if isinstance(
                        interpretation, uproot.interpretation.identify.UnknownInterpretation
                    ):
                    logging.getLogger(__name__).warning(
                        f"Skipping {branch.name} as it is not interpretable by Uproot"
                    )
                    return False
        if isinstance(branch.interpretation, uproot.interpretation.identify.UnknownInterpretation):
            logging.getLogger(__name__).warning(
                f"Skipping {branch.name} as it is not interpretable by Uproot"
            )
            return False
        try:
            _ = branch.interpretation.awkward_form(None)
        except uproot.interpretation.objects.CannotBeAwkward:
            logging.getLogger(__name__).warning(
                f"Skipping {branch.name} as it cannot be represented as an Awkward array"
            )
            return False
        else:
            return True

    return (lambda selection: dak.zip({key: (dak.zip(value, depth_limit=(None if len(value) == 1 else 1)) if isinstance(value, dict) else value) for key, value in selection.items()} if isinstance(selection, dict) else selection, depth_limit=(None if len(selection) == 1 else 1)) if not isinstance(selection, dak.Array) else selection)((lambda e: {'el_pt_NOSYS': e['el_pt_NOSYS']})((lambda input_files, tree_name_to_use: (logging.getLogger(__name__).info('Using treename=' + repr(tree_name_to_use)), uproot.dask({input_file: tree_name_to_use for input_file in input_files}, filter_branch=_remove_not_interpretable))[1])((lambda source: [source] if isinstance(source, str) else source)(input_filenames if input_filenames is not None else ['bogus.root']), tree_name if tree_name is not None else 'reco'))).compute()
